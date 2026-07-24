import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DriveSync:
    """Manages uploading videos to Google Drive."""

    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    def __init__(self, service_account_json: str, folder_id: str):
        """
        Initialize Drive sync.

        Args:
            service_account_json: Path to service account JSON file
            folder_id: Google Drive folder ID where videos will be uploaded
        """
        self.service_account_json = service_account_json
        self.folder_id = folder_id
        self.service = None

        if not os.path.exists(service_account_json):
            logger.warning(f"Service account file not found: {service_account_json}")
            logger.info("GDrive integration disabled. See SETUP for configuration.")
            return

        try:
            self._authenticate()
            logger.info(f"✓ Google Drive authenticated")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Drive: {e}")
            self.service = None

    def _authenticate(self):
        """Authenticate using service account."""
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_json,
            scopes=self.SCOPES
        )
        self.service = build('drive', 'v3', credentials=credentials)

    def upload_video(self, video_path: str, rhyme_title: str, video_type: str = "long") -> Optional[str]:
        """
        Upload a video to Google Drive.

        Args:
            video_path: Path to video file
            rhyme_title: Title of the rhyme (for naming)
            video_type: "long" or "short"

        Returns:
            Google Drive file ID if successful, None otherwise
        """
        if not self.service:
            logger.warning("Google Drive not authenticated. Skipping upload.")
            return None

        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None

        filename = Path(video_path).name
        file_size = os.path.getsize(video_path)
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Uploading {video_type} video: {filename} ({file_size_mb:.1f} MB)")

        try:
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id],
                'description': f"{rhyme_title} - {video_type} form video"
            }

            media = MediaFileUpload(
                video_path,
                mimetype='video/mp4',
                resumable=True,
                chunksize=262144 * 10  # 2.5MB chunks
            )

            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            )

            response = None
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(100 * status.progress())
                        logger.info(f"  {progress}% uploaded")
                except Exception as e:
                    logger.error(f"Upload error: {e}")
                    return None

            file_id = response.get('id')
            drive_link = response.get('webViewLink')

            logger.info(f"✓ Uploaded to Drive: {drive_link}")
            return file_id

        except Exception as e:
            logger.error(f"Failed to upload video: {e}")
            return None

    def upload_video_pair(self, rhyme_id: str, long_video_path: str, short_video_path: str, rhyme_title: str) -> Dict:
        """
        Upload both long and short form videos.

        Returns:
            Dict with keys 'long_id', 'short_id', 'long_link', 'short_link'
        """
        result = {
            "long_id": None,
            "short_id": None,
            "long_link": None,
            "short_link": None
        }

        # Upload long-form
        logger.info(f"[{rhyme_id}] Uploading long-form video...")
        result["long_id"] = self.upload_video(long_video_path, rhyme_title, "long")
        if result["long_id"]:
            result["long_link"] = f"https://drive.google.com/file/d/{result['long_id']}/view"

        # Upload short-form
        logger.info(f"[{rhyme_id}] Uploading short-form video...")
        result["short_id"] = self.upload_video(short_video_path, rhyme_title, "short")
        if result["short_id"]:
            result["short_link"] = f"https://drive.google.com/file/d/{result['short_id']}/view"

        return result

    def is_authenticated(self) -> bool:
        """Check if Drive service is authenticated."""
        return self.service is not None


if __name__ == "__main__":
    import sys

    # Test drive sync
    service_account_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "service-account.json")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    if not folder_id:
        print("ERROR: GOOGLE_DRIVE_FOLDER_ID not set")
        print("Set it in config.env")
        sys.exit(1)

    drive = DriveSync(service_account_json, folder_id)

    if drive.is_authenticated():
        print("✓ Google Drive authenticated successfully")
    else:
        print("✗ Google Drive authentication failed")
        print("  Make sure service-account.json exists and is valid")
