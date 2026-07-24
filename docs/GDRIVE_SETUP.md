# Google Drive Integration Setup

Auto-sync generated videos to Google Drive using Service Account authentication.

## Why Service Account?

- ✅ Zero user interaction (runs automatically)
- ✅ Server-to-server auth (no OAuth popups)
- ✅ Perfect for unattended scheduling
- ✅ No credential expiration

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project: **Nursery Rhymes Video**
3. Enable the **Google Drive API**:
   - Go to **APIs & Services** → **Library**
   - Search for "Google Drive API"
   - Click **Enable**

## Step 2: Create Service Account

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **Service Account**
3. Fill in:
   - **Service account name**: `nursery-rhymes-bot`
   - **Service account ID**: `nursery-rhymes-bot@...` (auto-generated)
4. Click **Create and Continue**
5. Skip optional steps
6. Click **Create Key**:
   - Key type: **JSON**
   - Downloads `service-account.json`

**⚠️ IMPORTANT**: Keep this file secure!

## Step 3: Create Google Drive Folder

1. Go to [Google Drive](https://drive.google.com)
2. Create folder: **Nursery Rhymes Videos**
3. Right-click → **Share**
4. Paste service account email from `service-account.json`:
   ```
   nursery-rhymes-bot@[PROJECT-ID].iam.gserviceaccount.com
   ```
5. Give **Editor** access

## Step 4: Get Folder ID

1. Open the folder in Google Drive
2. URL: `https://drive.google.com/drive/folders/{FOLDER_ID}`
3. Copy `FOLDER_ID`

## Step 5: Configure

```bash
# Copy service account file
cp ~/Downloads/service-account.json ~/ai-nursery-rhymes/

# Edit config.env
cd ~/ai-nursery-rhymes
nano config.env
```

Add:
```env
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=./service-account.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here
```

## Step 6: Test

```bash
cd ~/ai-nursery-rhymes
source venv/bin/activate
python src/drive_sync.py
```

## How It Works

- Scheduler generates videos
- Drive sync auto-uploads to your folder
- Videos ready for YouTube scheduling immediately

