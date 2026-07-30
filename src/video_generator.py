import os
import json
import math
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import logging

import cartoon

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoGenerator:
    def __init__(self, output_dir: str = "./output", staging_dir: str = "./output/staging",
                 day: str = None):
        self.output_dir = Path(output_dir)
        self.staging_root = Path(staging_dir)
        self.day = day or datetime.now().strftime("%Y-%m-%d")

        # Finished videos land in a per-day folder so it is obvious at a glance
        # which ones still need uploading. Intermediates (TTS, frames, looped
        # audio) go to a separate work tree so they never clutter that view.
        self.staging_dir = self.staging_root / self.day
        self.work_dir = self.output_dir / "work" / self.day
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.pexels_api_key = os.getenv("PEXELS_API_KEY")

    # "Jessica - Playful, Bright, Warm", a premade voice. The previous default
    # (Rachel) is a *library* voice, which the API refuses on free plans.
    DEFAULT_VOICE_ID = "cgSgspJ2msm6clMCkdW9"

    def generate_tts_audio(self, text: str, voice_id: str = None) -> Tuple[str, float]:
        """Generate TTS audio using ElevenLabs."""
        voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", self.DEFAULT_VOICE_ID)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        # eleven_monolingual_v1 was retired by ElevenLabs and now 400s.
        data = {
            "text": text,
            "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        logger.info(f"Generating TTS audio...")
        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")

        audio_path = self.work_dir / f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.mp3"
        with open(audio_path, 'wb') as f:
            f.write(response.content)

        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1", str(audio_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            duration = float(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError):
            duration = len(text.split()) * 0.5

        logger.info(f"TTS audio generated: {audio_path} ({duration:.1f}s)")
        return str(audio_path), duration

    def get_stock_images(self, keywords: str, count: int = 5) -> list:
        """Fetch stock images from Pexels."""
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": self.pexels_api_key}
        params = {"query": keywords, "per_page": count}

        logger.info(f"Fetching stock images for: {keywords}")
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            logger.warning(f"Pexels API error: {response.status_code}")
            return []

        data = response.json()
        image_urls = [photo["src"]["medium"] for photo in data.get("photos", [])]
        logger.info(f"Found {len(image_urls)} stock images")
        return image_urls

    TITLE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    SUBTITLE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    @staticmethod
    def _wrap_to_width(draw, text: str, font, max_width: int) -> List[str]:
        """Greedy word-wrap measured against the actual font metrics."""
        lines, current = [], ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if current and width > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def _fit_title(self, draw, title: str, max_width: int, max_lines: int = 3):
        """Find the largest font size at which the title fits the frame.

        A fixed 80px font overflowed 1080px on longer titles and was drawn at a
        negative x, clipping the first and last characters.
        """
        for size in range(88, 40, -4):
            try:
                font = ImageFont.truetype(self.TITLE_FONT, size)
            except OSError:
                return ImageFont.load_default(), [title]
            lines = self._wrap_to_width(draw, title, font, max_width)
            widest = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
            if len(lines) <= max_lines and widest <= max_width:
                return font, lines
        return font, lines

    def create_title_frame(self, title: str, duration_seconds: float = 3) -> str:
        """Create a colorful title frame."""
        width, height, margin = 1080, 1920, 60
        max_width = width - (2 * margin)

        img = Image.new('RGB', (width, height), color=(255, 200, 100))
        draw = ImageDraw.Draw(img)

        font, lines = self._fit_title(draw, title, max_width)
        try:
            small_font = ImageFont.truetype(self.SUBTITLE_FONT, 40)
        except OSError:
            small_font = ImageFont.load_default()

        line_height = int(font.size * 1.25)
        block_height = line_height * len(lines)
        y = (height // 2) - (block_height // 2)

        for line in lines:
            line_width = draw.textbbox((0, 0), line, font=font)[2]
            draw.text(((width - line_width) // 2, y), line, fill=(255, 255, 255), font=font)
            y += line_height

        subtitle = "Nursery Rhyme"
        sub_width = draw.textbbox((0, 0), subtitle, font=small_font)[2]
        draw.text(((width - sub_width) // 2, y + 30), subtitle,
                  fill=(255, 255, 255), font=small_font)

        img_path = self.work_dir / f"title_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.png"
        img.save(img_path)

        logger.info(f"Created title frame ({len(lines)} line(s) @ {font.size}px): {img_path}")
        return str(img_path)

    def download_image(self, url: str) -> str:
        """Download an image and save it locally."""
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(BytesIO(response.content)).convert("RGB")

            # Cover-crop rather than resize((1080,1920)), which stretched
            # landscape stock photos into distorted portraits. Scale so the
            # image covers the frame, then centre-crop the overflow.
            target_w, target_h = 1080, 1920
            scale = max(target_w / img.width, target_h / img.height)
            img = img.resize(
                (max(target_w, round(img.width * scale)),
                 max(target_h, round(img.height * scale))),
                Image.Resampling.LANCZOS,
            )
            left = (img.width - target_w) // 2
            top = (img.height - target_h) // 2
            img = img.crop((left, top, left + target_w, top + target_h))
            # Second-resolution timestamps collide when several images are
            # fetched in the same second, silently overwriting each other.
            img_path = self.work_dir / (
                f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
            )
            img.save(img_path)
            return str(img_path)
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
            return None

    def _build_frames(self, rhyme: Dict) -> List[str]:
        """Build the slideshow frames for a rhyme.

        Defaults to procedurally drawn cartoon art. Pexels returns real
        photography, which reads as adult/documentary and is wrong for a
        children's channel; set IMAGE_SOURCE=pexels to go back to it.
        """
        source = os.getenv("IMAGE_SOURCE", "cartoon").lower()
        theme = " ".join(rhyme.get("theme", []) or ["playful"])
        stem = f"{rhyme['id']}_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}"

        if source == "pexels":
            frames = [self.create_title_frame(rhyme["title"])]
            for url in self.get_stock_images(theme, count=4):
                downloaded = self.download_image(url)
                if downloaded:
                    frames.append(downloaded)
            return frames

        frames = [cartoon.title_card(
            rhyme["title"], str(self.work_dir / f"title_{stem}.png"), seed=hash(stem) & 0xFFFF
        )]
        # Alternate the rhyme's own theme with a generic playful scene so
        # successive frames are visibly different rather than near-identical.
        for i in range(4):
            scene_theme = theme if i % 2 == 0 else "playful"
            frames.append(cartoon.scene(
                scene_theme, str(self.work_dir / f"scene{i}_{stem}.png"), seed=i * 7 + 3
            ))
        return frames

    def _loop_audio(self, audio_path: str, audio_duration: float, target_seconds: float) -> str:
        """Repeat the narration until it fills target_seconds.

        A single reading of an 8-12 line rhyme is only ~30-45s, which is below
        the 60s floor that extract_shorts_from_long() requires. Repetition is
        native to the nursery-rhyme format, so we loop rather than pad silence.
        """
        if audio_duration <= 0:
            raise ValueError(f"cannot loop audio with duration {audio_duration}")

        repeats = max(1, math.ceil(target_seconds / audio_duration))
        looped_path = self.work_dir / f"looped_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.m4a"
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(repeats - 1), "-i", audio_path,
            "-t", f"{target_seconds:.2f}",
            "-c:a", "aac", "-b:a", "128k",
            str(looped_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        logger.info(
            f"Looped narration {repeats}x to {target_seconds:.0f}s "
            f"(single pass was {audio_duration:.1f}s)"
        )
        return str(looped_path)

    def _slideshow_args(self, frames: List[str], target_seconds: float) -> Tuple[List[str], str]:
        """Build ffmpeg inputs that hold each frame for an equal slice of the run.

        Uses one `-loop 1 -t` input per frame plus the concat *filter*, rather
        than the concat *demuxer*. The demuxer silently ignores its `duration`
        directives for still images and yields a ~1s video regardless.
        """
        per_frame = target_seconds / len(frames)
        args: List[str] = []
        for frame in frames:
            args += ["-loop", "1", "-t", f"{per_frame:.3f}", "-i", frame]
        streams = "".join(f"[{i}:v]" for i in range(len(frames)))
        filtergraph = (
            f"{streams}concat=n={len(frames)}:v=1:a=0,"
            f"scale=1080:1920,fps=30[v]"
        )
        return args, filtergraph

    def generate_long_form_video(self, rhyme: Dict) -> str:
        """Generate long-form video (3-5 min) from a rhyme."""
        logger.info(f"Generating long-form video for: {rhyme['title']}")
        target_seconds = float(os.getenv("LONG_FORM_TARGET_SECONDS", "210"))

        audio_path, audio_duration = self.generate_tts_audio(rhyme['text'])
        looped_audio = self._loop_audio(audio_path, audio_duration, target_seconds)

        frames = self._build_frames(rhyme)
        logger.info(f"Slideshow has {len(frames)} frame(s)")

        slideshow_args, filtergraph = self._slideshow_args(frames, target_seconds)
        output_path = self.staging_dir / f"{rhyme['id']}_long_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        cmd = (
            ["ffmpeg", "-y"]
            + slideshow_args
            + ["-i", looped_audio,
               "-filter_complex", filtergraph,
               "-map", "[v]", "-map", f"{len(frames)}:a",
               "-c:v", "libx264", "-c:a", "aac", "-shortest",
               "-pix_fmt", "yuv420p",
               str(output_path)]
        )
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            logger.info(f"Long-form video created: {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise
        return str(output_path)

    def extract_shorts_from_long(self, long_video_path: str, num_shorts: int = 2) -> List[str]:
        """
        Extract short-form clips from a long-form video.

        Args:
            long_video_path: Path to long-form MP4
            num_shorts: Number of short clips to extract (default: 2)

        Returns:
            List of short video file paths
        """
        logger.info(f"Extracting {num_shorts} short-form videos from long-form...")

        if not os.path.exists(long_video_path):
            logger.error(f"Long video not found: {long_video_path}")
            return []

        # Get duration of long-form video
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1", long_video_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            duration = float(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError):
            logger.error("Failed to get video duration")
            return []

        if duration < 60:
            logger.warning("Long-form video is less than 60 seconds, skipping shorts extraction")
            return []

        short_paths = []

        if num_shorts >= 1:
            # Clip 1: From 20s to 60s (40 seconds) - early part
            short_path_1 = self.staging_dir / f"{Path(long_video_path).stem}_short_1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            cmd = [
                "ffmpeg", "-y", "-i", long_video_path,
                "-ss", "20", "-to", "60",
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-vf", "scale=1080:1920",
                str(short_path_1)
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=60)
                short_paths.append(str(short_path_1))
                logger.info(f"✓ Short clip 1 created: {short_path_1}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create short clip 1: {e.stderr.decode()}")

        if num_shorts >= 2:
            # Clip 2: From (duration - 50s) to end - late part
            start_time = max(60, duration - 50)
            short_path_2 = self.staging_dir / f"{Path(long_video_path).stem}_short_2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            cmd = [
                "ffmpeg", "-y", "-i", long_video_path,
                "-ss", str(start_time), "-to", str(duration),
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", "-vf", "scale=1080:1920",
                str(short_path_2)
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=60)
                short_paths.append(str(short_path_2))
                logger.info(f"✓ Short clip 2 created: {short_path_2}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create short clip 2: {e.stderr.decode()}")

        logger.info(f"Extracted {len(short_paths)} short-form videos")
        return short_paths
