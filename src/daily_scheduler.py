import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json

from rhyme_manager import RhymeManager
from video_generator import VideoGenerator
from upload_queue import UploadQueue
from drive_sync import DriveSync

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./logs/scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DailyScheduler:
    def __init__(self):
        self.rhyme_manager = RhymeManager(data_dir="./data")
        self.video_generator = VideoGenerator(output_dir="./output", staging_dir="./output/staging")
        self.upload_queue = UploadQueue(queue_file="./upload_queue.json")
        self.videos_per_day = int(os.getenv("VIDEOS_PER_DAY", 5))
        self.job_time = os.getenv("DAILY_JOB_TIME", "06:00")
        self.scheduler = BackgroundScheduler()

        # Initialize Google Drive sync (optional)
        service_account_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
        drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        if service_account_json and drive_folder_id:
            self.drive_sync = DriveSync(service_account_json, drive_folder_id)
        else:
            self.drive_sync = None

    def generate_daily_videos(self):
        """Main job: Generate 5 videos (5 long-form + 5 short-form)."""
        logger.info("=" * 60)
        logger.info("Starting daily video generation job")
        logger.info("=" * 60)
        generated_videos = []

        try:
            for i in range(self.videos_per_day):
                logger.info(f"\n[{i+1}/{self.videos_per_day}] Generating video pair...")
                source = "popular" if i < 3 else "generated"

                if source == "generated":
                    logger.info("Generating new AI rhyme...")
                    rhyme = self.rhyme_manager.generate_new_rhyme(theme=None, age_group="2-5")
                else:
                    rhyme = self.rhyme_manager.get_random_rhyme(source="popular")
                    logger.info(f"Selected popular rhyme: {rhyme['title']}")

                try:
                    logger.info(f"Generating long-form video...")
                    long_video = self.video_generator.generate_video(rhyme, video_type="long")
                    logger.info(f"Generating short-form video...")
                    short_video = self.video_generator.generate_video(rhyme, video_type="short")

                    self.upload_queue.add_videos(
                        rhyme_id=rhyme["id"],
                        long_video_path=long_video,
                        short_video_path=short_video,
                        rhyme_data=rhyme
                    )

                    generated_videos.append({
                        "title": rhyme["title"],
                        "rhyme_id": rhyme["id"],
                        "long_video": long_video,
                        "short_video": short_video
                    })

                    logger.info(f"✓ Successfully generated: {rhyme['title']}")
                except Exception as e:
                    logger.error(f"✗ Failed to generate video #{i+1}: {e}", exc_info=True)
                    continue

            self._notify_videos_ready(generated_videos)
        except Exception as e:
            logger.error(f"Daily job failed: {e}", exc_info=True)

        logger.info("=" * 60)
        logger.info("Daily video generation job complete")
        logger.info("=" * 60)

    def _notify_videos_ready(self, videos: list):
        """Create a notification that videos are ready for upload."""
        queue_summary = self.upload_queue.get_queue_summary()
        
        # Count actual videos (long + shorts)
        total_longs = len(videos)
        total_shorts = sum(v.get("short_count", 2) for v in videos)
        total_videos = total_longs + total_shorts
        
        # Add Drive upload status if available
        drive_status = ""
        if self.drive_sync and self.drive_sync.is_authenticated():
            drive_status = "\n✓ Videos uploaded to Google Drive automatically!"
        
        notification = {
            "timestamp": datetime.now().isoformat(),
            "generated_today": len(videos),
            "total_longs": total_longs,
            "total_shorts": total_shorts,
            "total_videos": total_videos,
            "total_pending": queue_summary["pending_videos"],
            "videos": videos,
            "message": f"🎬 Video generation complete!\n\nGenerated today: {total_longs} long-form + {total_shorts} short-form = {total_videos} videos\nTotal pending upload: {queue_summary['pending_videos']}{drive_status}\n\nRun `python check_queue.py` to view the queue."
        }

        notification_file = f"./notifications/ready_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("./notifications", exist_ok=True)
        with open(notification_file, 'w') as f:
            json.dump(notification, f, indent=2)

        logger.info(f"\n{'='*60}")
        logger.info("📺 VIDEOS READY FOR UPLOAD!")
        logger.info(f"{'='*60}")
        logger.info(notification["message"])
        logger.info(f"{'='*60}\n")

        print("\n" + "=" * 60)
        print("📺 VIDEOS READY FOR UPLOAD!")
        print("=" * 60)
        print(notification["message"])
        print("=" * 60 + "\n")

    def start(self):
        """Start the daily scheduler."""
        hour, minute = map(int, self.job_time.split(":"))
        self.scheduler.add_job(
            self.generate_daily_videos,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_video_generation",
            name="Daily Video Generation",
            replace_existing=True
        )
        logger.info(f"Scheduler configured to run at {self.job_time} UTC every day")
        logger.info(f"Videos per day: {self.videos_per_day}")
        self.scheduler.start()
        logger.info("Scheduler started (running in background)")
        return self.scheduler

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    def run_now(self):
        """Manually trigger the job right now."""
        logger.info("Manually triggering daily video generation...")
        self.generate_daily_videos()
