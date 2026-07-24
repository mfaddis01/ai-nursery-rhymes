import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UploadQueue:
    """Manages the queue of videos ready for upload to YouTube."""

    def __init__(self, queue_file: str = "./upload_queue.json"):
        self.queue_file = Path(queue_file)
        self.queue = self._load_queue()

    def _load_queue(self) -> List[Dict]:
        """Load the queue from disk."""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_queue(self):
        """Save the queue to disk."""
        with open(self.queue_file, 'w') as f:
            json.dump(self.queue, f, indent=2)

    def add_video_pair(self, rhyme_id: str, long_video_path: str, short_video_path: str, 
                       rhyme_data: Dict, short_variant: int = 1):
        """
        Add a video pair (long + 1 short variant) to the queue.

        Args:
            rhyme_id: Unique identifier (can include variant, e.g., "twinkle_short_1")
            long_video_path: Path to long-form video
            short_video_path: Path to short-form video variant
            rhyme_data: The rhyme data dict
            short_variant: Which short variant (1 or 2)
        """
        entry = {
            "rhyme_id": rhyme_id,
            "long_video_path": long_video_path,
            "short_video_path": short_video_path,
            "short_variant": short_variant,
            "title": rhyme_data.get("title"),
            "theme": rhyme_data.get("theme"),
            "age_group": rhyme_data.get("age_group"),
            "type": "short",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "uploaded_at": None,
            "youtube_video_id": None
        }

        self.queue.append(entry)
        self._save_queue()
        logger.info(f"Added to queue: {rhyme_id} (short variant {short_variant})")

    def add_videos(self, rhyme_id: str, long_video_path: str, short_video_path: str, rhyme_data: Dict):
        """Legacy method for backward compatibility."""
        self.add_video_pair(rhyme_id, long_video_path, short_video_path, rhyme_data)

    def get_pending_videos(self) -> List[Dict]:
        """Get all videos pending upload."""
        return [v for v in self.queue if v.get("status") == "pending"]

    def get_pending_shorts(self) -> List[Dict]:
        """Get all short-form videos pending upload."""
        return [v for v in self.queue if v.get("status") == "pending" and v.get("type") == "short"]

    def get_today_queue(self) -> List[Dict]:
        """Get videos generated today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return [v for v in self.queue if v.get("created_at", "").startswith(today)]

    def mark_uploaded(self, rhyme_id: str, youtube_video_id: str = None):
        """
        Mark a video as uploaded.

        Args:
            rhyme_id: The rhyme ID (can include variant)
            youtube_video_id: Optional YouTube video ID
        """
        for entry in self.queue:
            if entry.get("rhyme_id") == rhyme_id:
                entry["status"] = "uploaded"
                entry["uploaded_at"] = datetime.now().isoformat()
                if youtube_video_id:
                    entry["youtube_video_id"] = youtube_video_id
                self._save_queue()
                logger.info(f"Marked as uploaded: {rhyme_id}")
                return

    def get_queue_summary(self) -> Dict:
        """Get a summary of the queue status."""
        pending = self.get_pending_videos()
        shorts = self.get_pending_shorts()
        today = self.get_today_queue()

        return {
            "total_in_queue": len(self.queue),
            "pending_videos": len(pending),
            "pending_shorts": len(shorts),
            "generated_today": len(today),
            "pending_entries": pending
        }
