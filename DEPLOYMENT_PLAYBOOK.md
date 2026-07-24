# 🚀 Deployment Playbook: AI Nursery Rhymes

Complete step-by-step guide to deploy the system on WSL.

## Phase 1: Get API Keys (10 minutes)

### 1. Anthropic Claude API Key

```bash
# Open: https://console.anthropic.com
# → Create API key
# → Copy: sk-ant-...
```

### 2. ElevenLabs TTS Key

```bash
# Open: https://elevenlabs.io
# → Sign up (free tier: 10k chars/month = 5+ days of videos)
# → Get API key
```

### 3. Pexels API Key

```bash
# Open: https://www.pexels.com/api
# → Request access (free, instant)
# → Get API key
```

## Phase 2: Setup GDrive Integration (5-10 minutes)

### One-Command Setup

```bash
cd ~/ai-nursery-rhymes
bash setup_gdrive_interactive.sh
```

This will:
- ✓ Install Google Cloud CLI
- ✓ Create Google Cloud project
- ✓ Create service account
- ✓ Enable Drive API
- ✓ Create Drive folder
- ✓ Auto-configure config.env

### What Happens

1. Browser opens → Sign in with Google account
2. Service account created automatically
3. Drive folder created automatically
4. Everything auto-configured in config.env

**No manual Google Cloud steps needed!**

## Phase 3: Configure API Keys (2 minutes)

```bash
cd ~/ai-nursery-rhymes
nano config.env
```

Fill in your API keys:

```env
# Your keys go here
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
ELEVENLABS_API_KEY=your_elevenlabs_key
PEXELS_API_KEY=your_pexels_key
```

Save (Ctrl+X → Y → Enter)

## Phase 4: Install Dependencies (2 minutes)

```bash
cd ~/ai-nursery-rhymes

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all dependencies (including GDrive)
pip install -r requirements.txt

# Also install ffmpeg (needed for video rendering)
sudo apt-get install -y ffmpeg
```

## Phase 5: Test the System (2-5 minutes)

```bash
cd ~/ai-nursery-rhymes/src

# Generate 1 test video pair
python daily_scheduler.py test
```

You should see:
```
============================================================
Starting daily video generation job
============================================================

[1/1] Generating video pair...
Generating new AI rhyme...
Generating TTS audio...
Fetching stock images...
Generating long-form video...
Generating short-form video...
✓ Successfully generated: [rhyme title]

============================================================
📺 VIDEOS READY FOR UPLOAD!
============================================================
🎬 1 video pairs are ready for upload!

Videos generated today: 1
Total pending upload: 1
✓ Videos uploaded to Google Drive automatically!
```

Check the queue:
```bash
cd ~/ai-nursery-rhymes
python src/check_queue.py
```

Check your Google Drive folder - videos should be there!

## Phase 6: Deploy (30 seconds)

### Option A: Run in Background (Recommended)

```bash
cd ~/ai-nursery-rhymes/src
python daily_scheduler.py &
```

This runs in the background and generates videos daily at 06:00 UTC.

### Option B: Keep Terminal Open

```bash
cd ~/ai-nursery-rhymes/src
python daily_scheduler.py
```

Keep terminal open. Press Ctrl+C to stop.

### Option C: Run as Service (Advanced)

Create systemd service for persistent deployment:

```bash
sudo tee /etc/systemd/user/nursery-rhymes.service > /dev/null << 'SERVICE'
[Unit]
Description=AI Nursery Rhymes Video Generator
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/svc_ppc/ai-nursery-rhymes
Environment="PATH=/home/svc_ppc/ai-nursery-rhymes/venv/bin"
ExecStart=/home/svc_ppc/ai-nursery-rhymes/venv/bin/python src/daily_scheduler.py
Restart=on-failure
RestartSec=300

[Install]
WantedBy=default.target
SERVICE

# Enable and start
systemctl --user daemon-reload
systemctl --user enable nursery-rhymes
systemctl --user start nursery-rhymes

# Check status
systemctl --user status nursery-rhymes
```

## Phase 7: Daily Operations (30 seconds/day)

### Every Day at 06:00 UTC

Scheduler automatically:
1. ✓ Generates 5 AI rhymes + picks 5 popular ones
2. ✓ Creates TTS audio
3. ✓ Renders long-form + short-form videos
4. ✓ Uploads to Google Drive
5. ✓ Updates queue with upload status

### Check Status

```bash
cd ~/ai-nursery-rhymes
python src/check_queue.py
```

Shows:
- How many videos are pending
- Links to Google Drive files
- Upload timestamps

### Download & Upload to YouTube

1. Open Google Drive folder
2. Download 1 long-form + 1 short-form video
3. Upload to YouTube Studio
4. Schedule for your preferred time
5. Run: `python src/mark_uploaded.py <rhyme_id>`

### View Logs

```bash
tail -f ~/ai-nursery-rhymes/logs/scheduler.log
```

Shows all generation details, errors, and status.

## Troubleshooting

### "API key invalid"

```bash
# Verify key is in config.env
grep ANTHROPIC_API_KEY ~/ai-nursery-rhymes/config.env

# Regenerate key if needed
# Visit: https://console.anthropic.com
```

### "Videos not uploading to Drive"

```bash
# Check if GDrive is configured
grep GOOGLE_DRIVE ~/ai-nursery-rhymes/config.env

# Test Drive connection
cd ~/ai-nursery-rhymes/src
python -c "from drive_sync import DriveSync; print(DriveSync('./service-account.json', 'folder_id').is_authenticated())"
```

### "FFmpeg not found"

```bash
# Install ffmpeg
sudo apt-get install -y ffmpeg

# Verify
ffmpeg -version
```

### "gcloud command not found"

```bash
# Reinstall Google Cloud CLI
curl https://sdk.cloud.google.com | bash
```

## Success Checklist

- [ ] API keys obtained (Claude, ElevenLabs, Pexels)
- [ ] GDrive setup script completed successfully
- [ ] config.env has all API keys
- [ ] Virtual environment created and activated
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] FFmpeg installed: `sudo apt-get install -y ffmpeg`
- [ ] Test generation passed: `python daily_scheduler.py test`
- [ ] Videos appeared in Google Drive
- [ ] Scheduler deployed: `python daily_scheduler.py &`
- [ ] Daily cron job confirmed to run at 06:00 UTC

## You're Live! 🎉

Videos will generate automatically every day at 06:00 UTC and upload to your Google Drive folder.

### Next Steps

1. **Monitor** first week for any issues
2. **Adjust** schedule if needed (edit config.env: DAILY_JOB_TIME)
3. **Download & Upload** to YouTube daily (or automate later)
4. **Track** engagement to see what rhymes perform best

---

**Estimated Total Setup Time**: 30 minutes
**Estimated Daily Maintenance**: 30 seconds (just check queue + upload 5-10 videos)

