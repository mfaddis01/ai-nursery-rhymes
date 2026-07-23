# Setup Guide: AI Nursery Rhyme Generator (WSL)

Step-by-step setup on Windows Subsystem for Linux.

## Prerequisites

- WSL2 with Ubuntu
- Python 3.9+
- ffmpeg
- Git

### Install Dependencies

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg git
```

## Step 1: Get API Keys

### Anthropic (Claude)
1. Go to https://console.anthropic.com
2. Create API key
3. Paste into config.env

### ElevenLabs (TTS)
1. Go to https://elevenlabs.io
2. Free tier: 10k characters/month (plenty for 5 videos/day)
3. Get API key, paste into config.env

### Pexels (Stock Images)
1. Go to https://www.pexels.com/api
2. Request access (free)
3. Get API key, paste into config.env

## Step 2: Setup Project

```bash
# Navigate to project
cd ~/ai-nursery-rhymes

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup config
cp config.env.example config.env
# Edit config.env with your API keys
nano config.env
```

## Step 3: Test

```bash
cd src
python daily_scheduler.py test
```

Should generate 1 complete video pair (long + short).

## Step 4: Start Scheduler

```bash
cd src
python daily_scheduler.py
```

Runs in background, generating videos daily at your scheduled time.

## Step 5: Check Queue

```bash
cd ~/ai-nursery-rhymes
python src/check_queue.py
```

Shows pending videos ready for upload.

## GDrive Integration (Phase 2)

Coming soon: Auto-sync videos to Google Drive.

