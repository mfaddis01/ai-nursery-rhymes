import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoGenerator:
    def __init__(self, output_dir: str = "./output", staging_dir: str = "./output/staging"):
        self.output_dir = Path(output_dir)
        self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.pexels_api_key = os.getenv("PEXELS_API_KEY")

    def generate_tts_audio(self, text: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> Tuple[str, float]:
        """Generate TTS audio using ElevenLabs."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        logger.info(f"Generating TTS audio...")
        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")

        audio_path = self.staging_dir / f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
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

    def create_title_frame(self, title: str, duration_seconds: float = 3) -> str:
        """Create a colorful title frame."""
        img = Image.new('RGB', (1080, 1920), color=(255, 200, 100))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), title, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = (1080 - text_width) // 2
        draw.text((text_x, 800), title, fill=(255, 255, 255), font=font)
        draw.text((540 - 100, 950), "Nursery Rhyme", fill=(255, 255, 255), font=small_font)

        img_path = self.staging_dir / f"title_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img.save(img_path)

        logger.info(f"Created title frame: {img_path}")
        return str(img_path)

    def download_image(self, url: str) -> str:
        """Download an image and save it locally."""
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(BytesIO(response.content))
            img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
            img_path = self.staging_dir / f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            img.save(img_path)
            return str(img_path)
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
            return None

    def generate_long_form_video(self, rhyme: Dict) -> str:
        """Generate long-form video (3-5 min) from a rhyme."""
        logger.info(f"Generating long-form video for: {rhyme['title']}")
        audio_path, audio_duration = self.generate_tts_audio(rhyme['text'])
        keywords = " ".join(rhyme.get("theme", ["nursery rhyme"]))
        image_urls = self.get_stock_images(keywords, count=3)
        title_frame = self.create_title_frame(rhyme['title'])

        output_path = self.staging_dir / f"{rhyme['id']}_long_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", audio_path, "-i", title_frame,
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            "-pix_fmt", "yuv420p", "-vf", "scale=1080:1920",
            str(output_path)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
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
