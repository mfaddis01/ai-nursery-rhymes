import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DriveSync:
    """Manages uploading videos to Google Drive."""

    # Full drive scope: drive.file only grants access to files the app itself
    # created, which makes uploading into a pre-existing folder unreliable.
    # Tighten to drive.file if the destination folder is app-created.
    SCOPES = [os.getenv("GOOGLE_DRIVE_SCOPE", "https://www.googleapis.com/auth/drive")]

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
        self.auth_mode = "unauthenticated"
        self._day_folder_cache = {}

        if self._is_placeholder(folder_id):
            logger.info("GOOGLE_DRIVE_FOLDER_ID not configured. GDrive integration disabled.")
            return

        try:
            self._authenticate()
            logger.info(f"✓ Google Drive authenticated ({self.auth_mode})")
        except DefaultCredentialsError:
            # Not an error - Drive is simply not set up on this host yet.
            logger.info(
                "No Google credentials found. GDrive integration disabled. "
                "Run: gcloud auth application-default login "
                "--scopes=https://www.googleapis.com/auth/drive,"
                "https://www.googleapis.com/auth/cloud-platform"
            )
            self.service = None
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Drive: {e}")
            self.service = None

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        """True when a config value is absent or still the shipped placeholder."""
        if not value or not value.strip():
            return True
        v = value.strip().lower()
        return v.startswith("your_") or v.endswith("_here") or v in {"none", "changeme"}

    def _authenticate(self):
        """Authenticate with a service account key, or fall back to ADC.

        Many Google Cloud orgs enforce
        constraints/iam.managed.disableServiceAccountKeyCreation, which makes a
        service account key impossible to mint. Application Default Credentials
        authenticate as the user instead - which also sidesteps the fact that
        service accounts have no Drive storage quota, since files are then
        owned by the user rather than the service account.
        """
        has_key = (
            self.service_account_json
            and os.path.exists(self.service_account_json)
            and os.path.getsize(self.service_account_json) > 0
        )
        if has_key:
            self.auth_mode = "service account"
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_json,
                scopes=self.SCOPES
            )
        else:
            import google.auth
            self.auth_mode = "application default credentials"
            # Scopes already granted at `gcloud auth application-default login`
            # time are what actually apply for user credentials.
            credentials, _ = google.auth.default(scopes=self.SCOPES)

        self.service = build('drive', 'v3', credentials=credentials)

    FOLDER_MIME = "application/vnd.google-apps.folder"

    @staticmethod
    def _escape(name: str) -> str:
        """Escape a literal for a Drive query string."""
        return name.replace("\\", "\\\\").replace("'", "\\'")

    def _find_child(self, parent: str, name: str, mime: str = None) -> Optional[str]:
        """Return the id of a non-trashed child by exact name, or None."""
        q = f"'{parent}' in parents and name = '{self._escape(name)}' and trashed = false"
        if mime:
            q += f" and mimeType = '{mime}'"
        res = self.service.files().list(
            q=q, fields="files(id)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def day_folder_id(self, day: str = None) -> str:
        """Find or create the YYYY-MM-DD subfolder for a run's output.

        Grouping by day makes it obvious which videos still need uploading,
        instead of one flat folder that grows by 15 files a day.
        """
        day = day or datetime.now().strftime("%Y-%m-%d")
        if self._day_folder_cache.get(day):
            return self._day_folder_cache[day]

        found = self._find_child(self.folder_id, day, self.FOLDER_MIME)
        if not found:
            created = self.service.files().create(
                body={"name": day, "mimeType": self.FOLDER_MIME, "parents": [self.folder_id]},
                fields="id", supportsAllDrives=True,
            ).execute()
            found = created["id"]
            logger.info(f"Created Drive folder for {day}")

        self._day_folder_cache[day] = found
        return found

    def upload_video(self, video_path: str, rhyme_title: str, video_type: str = "long",
                     day: str = None) -> Optional[str]:
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

        try:
            # `day` lets a backfill file older output under its own date
            # instead of today's folder.
            parent = self.day_folder_id(day)
        except Exception as e:
            logger.error(f"Could not resolve the day folder: {e}")
            return None

        # Drive allows duplicate names, so an unconditional create() would add a
        # second copy of every file on any re-run or retry.
        existing = self._find_child(parent, filename)
        if existing:
            logger.info(f"Already in Drive, skipping: {filename}")
            return existing

        logger.info(f"Uploading {video_type} video: {filename} ({file_size_mb:.1f} MB)")

        try:
            file_metadata = {
                'name': filename,
                'parents': [parent],
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
                fields='id, webViewLink',
                # Required to write into a Shared Drive. Without it the API only
                # targets My Drive, where a service account has no storage quota
                # and every upload fails with storageQuotaExceeded.
                supportsAllDrives=True,
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
