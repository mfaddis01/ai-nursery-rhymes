"""
AI Nursery Rhyme Video Generation System
"""

__version__ = "0.1.0"

from rhyme_manager import RhymeManager
from video_generator import VideoGenerator
from upload_queue import UploadQueue
from daily_scheduler import DailyScheduler

__all__ = [
    "RhymeManager",
    "VideoGenerator",
    "UploadQueue",
    "DailyScheduler",
]
