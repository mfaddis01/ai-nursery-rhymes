# 🎬 AI Nursery Rhyme Video Generator

Automated system to generate and sync 5 long-form (3-5 min) + 5 short-form (<60s) nursery rhyme videos daily to Google Drive.

## Features

✨ **Automated Video Generation**
- AI-generated original rhymes (via Claude)
- Popular classic nursery rhymes
- Text-to-speech audio (ElevenLabs)
- Stock image/video sourcing (Pexels)
- Professional video rendering (ffmpeg)

📁 **Google Drive Auto-Sync**
- Uploads videos immediately after generation
- Service Account auth (zero user interaction)
- Ready for YouTube scheduling from anywhere

⏰ **Daily Automation**
- Runs at your scheduled time (default: 06:00 UTC)
- Generates 5 long-form + 5 short-form videos
- Tracks upload status
- Full logging and notifications

## Quick Start

### 1. Setup

```bash
cd ~/ai-nursery-rhymes
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.env.example config.env
nano config.env
# Add API keys for Claude, ElevenLabs, Pexels
# (Google Drive is optional for now)
```

### 3. Test

```bash
cd src
python daily_scheduler.py test
```

### 4. Run

```bash
python daily_scheduler.py
```

Runs daily at your scheduled time in the background.

## Workflow

```
06:00 UTC Daily:
  Generate 5 AI rhymes + pick 5 popular ones
         ↓
  Create TTS audio + render videos (long + short)
         ↓
  Upload to Google Drive automatically
         ↓
  Videos ready for YouTube scheduling
```

## Google Drive Integration

Enable auto-upload to Google Drive. See [docs/GDRIVE_SETUP.md](docs/GDRIVE_SETUP.md).

## Project Structure

```
ai-nursery-rhymes/
├── src/
│   ├── rhyme_manager.py      # Load & generate rhymes
│   ├── video_generator.py    # TTS + video rendering
│   ├── drive_sync.py         # Google Drive upload
│   ├── upload_queue.py       # Track videos
│   ├── daily_scheduler.py    # Main automation loop
│   ├── check_queue.py        # View pending videos
│   └── mark_uploaded.py      # Track uploaded videos
├── data/
│   ├── popular_rhymes.json
│   └── generated_rhymes.json
├── docs/
│   └── GDRIVE_SETUP.md       # Google Drive integration guide
├── config.env.example        # Configuration template
└── README.md
```

## Next Steps

1. **Get API keys** (Claude, ElevenLabs, Pexels) — free tiers available
2. **Test locally** — run `python daily_scheduler.py test`
3. **Setup Google Drive** (optional) — see [GDRIVE_SETUP.md](docs/GDRIVE_SETUP.md)
4. **Deploy** — keep scheduler running in background
5. **Schedule uploads** — download from Drive and upload to YouTube daily

## Cost Estimate

| Service | Cost/Day | Cost/Month |
|---------|----------|-----------|
| Claude | ~$0.01 | ~$0.30 |
| ElevenLabs | Free tier (10k chars/mo) | $0 |
| Pexels | Free | $0 |
| **Total** | **~$0.01** | **~$0.30** |

## Documentation

- [SETUP.md](SETUP.md) — Detailed setup instructions
- [docs/GDRIVE_SETUP.md](docs/GDRIVE_SETUP.md) — Google Drive integration
- [src/check_queue.py](src/check_queue.py) — View video queue

