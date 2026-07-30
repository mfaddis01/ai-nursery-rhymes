import os
import random
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
        # Only the folder id is required: without a service account key,
        # DriveSync falls back to Application Default Credentials.
        if drive_folder_id:
            self.drive_sync = DriveSync(service_account_json, drive_folder_id)
        else:
            self.drive_sync = None

    def generate_daily_videos(self, count: int = None, force_source: str = None):
        """Main job: generate `count` long-form videos, each with 2 extracted shorts.

        count/force_source are overrides for the `test` entrypoints; the
        scheduled run leaves both unset.
        """
        total = self.videos_per_day if count is None else count
        logger.info("=" * 60)
        logger.info("Starting daily video generation job")
        logger.info("=" * 60)
        generated_videos = []

        sources = [force_source or ("popular" if i < 3 else "generated") for i in range(total)]
        popular_picks = self._distinct_popular(sources.count("popular"))

        try:
            for i in range(total):
                logger.info(f"\n[{i+1}/{total}] Generating video pair...")
                source = sources[i]

                if source == "generated":
                    logger.info("Generating new AI rhyme...")
                    rhyme = self.rhyme_manager.generate_new_rhyme(theme=None, age_group="2-5")
                else:
                    rhyme = popular_picks.pop(0)
                    logger.info(f"Selected popular rhyme: {rhyme['title']}")

                try:
                    logger.info(f"Generating long-form video...")
                    long_video = self.video_generator.generate_long_form_video(rhyme)

                    logger.info(f"Extracting short-form videos...")
                    shorts = self.video_generator.extract_shorts_from_long(
                        long_video, num_shorts=2, rhyme=rhyme
                    )
                    if not shorts:
                        raise RuntimeError(
                            "no shorts extracted from long-form video "
                            f"({long_video}) - check its duration is over 60s"
                        )

                    for variant, short_video in enumerate(shorts, start=1):
                        self.upload_queue.add_video_pair(
                            rhyme_id=f"{rhyme['id']}_short_{variant}",
                            long_video_path=long_video,
                            short_video_path=short_video,
                            rhyme_data=rhyme,
                            short_variant=variant,
                        )

                    self._sync_to_drive(rhyme, long_video, shorts)

                    generated_videos.append({
                        "title": rhyme["title"],
                        "rhyme_id": rhyme["id"],
                        "long_video": long_video,
                        "short_videos": shorts,
                        "short_count": len(shorts),
                    })

                    logger.info(
                        f"✓ Successfully generated: {rhyme['title']} "
                        f"(1 long + {len(shorts)} shorts)"
                    )
                except Exception as e:
                    logger.error(f"✗ Failed to generate video #{i+1}: {e}", exc_info=True)
                    continue

            self._notify_videos_ready(generated_videos)
        except Exception as e:
            logger.error(f"Daily job failed: {e}", exc_info=True)

        logger.info("=" * 60)
        logger.info("Daily video generation job complete")
        logger.info("=" * 60)

        # Every per-video failure is caught and logged above so one bad rhyme
        # doesn't sink the batch. Producing nothing at all is a real failure
        # though, and the caller needs a non-zero exit so systemd flags it.
        return len(generated_videos)

    def _distinct_popular(self, count: int) -> list:
        """Pick `count` popular rhymes without repetition.

        get_random_rhyme() samples with replacement, so a batch could publish
        the same rhyme several times in one day.
        """
        pool = list(self.rhyme_manager.popular_rhymes)
        if not pool or count <= 0:
            return []
        if count <= len(pool):
            return random.sample(pool, count)
        logger.warning(
            f"Only {len(pool)} popular rhymes available for {count} slots; "
            "repeats are unavoidable until data/popular_rhymes.json grows."
        )
        picks = random.sample(pool, len(pool))
        while len(picks) < count:
            picks.append(random.choice(pool))
        return picks

    def _sync_to_drive(self, rhyme: dict, long_video: str, shorts: list):
        """Upload the long-form video and its shorts to Google Drive, if configured."""
        if not self.drive_sync or not self.drive_sync.is_authenticated():
            return
        try:
            self.drive_sync.upload_video(long_video, rhyme["title"], video_type="long")
            for variant, short_video in enumerate(shorts, start=1):
                self.drive_sync.upload_video(
                    short_video, f"{rhyme['title']} (short {variant})", video_type="short"
                )
            logger.info(f"Uploaded {1 + len(shorts)} file(s) to Google Drive")
        except Exception as e:
            # Drive is an optional mirror - never fail the run over it.
            logger.error(f"Google Drive upload failed: {e}", exc_info=True)

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
