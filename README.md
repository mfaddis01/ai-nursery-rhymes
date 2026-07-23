# 🎬 AI Nursery Rhyme Video Generator

Automated system to generate 5 long-form (3-5 min) + 5 short-form (<60s) nursery rhyme videos daily, ready for YouTube upload.

## 🚀 Quick Start

### 1. Setup

```bash
# Enter project directory
cd ~/ai-nursery-rhymes

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy config template and add API keys
cp config.env.example config.env
# Edit config.env with your API keys
```

### 2. Configure API Keys

Edit `config.env` with these keys:

- **Anthropic Claude**: https://console.anthropic.com
- **ElevenLabs TTS**: https://elevenlabs.io
- **Pexels Images**: https://www.pexels.com/api
- **Google Drive** (optional): Google Cloud Console

### 3. Test the System

```bash
cd src
python daily_scheduler.py test
```

### 4. Start Daily Automation

```bash
cd src
python daily_scheduler.py
```

Keep this running in the background to generate videos every day at your scheduled time.

## 📁 Project Structure

```
ai-nursery-rhymes/
├── config.env.example      # API key template
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── data/
│   ├── popular_rhymes.json
│   └── generated_rhymes.json
├── src/
│   ├── rhyme_manager.py
│   ├── video_generator.py
│   ├── upload_queue.py
│   ├── daily_scheduler.py
│   ├── check_queue.py
│   └── mark_uploaded.py
└── output/
    ├── staging/          # Generated videos
    └── uploaded/         # Uploaded videos (archive)
```

## 🎯 Daily Workflow

1. **Scheduler runs** (daily at configured time)
   - Generates 5 AI rhymes or picks popular ones
   - Creates TTS audio
   - Renders long-form + short-form videos
   - Saves to `output/staging/`

2. **Check the queue**
   ```bash
   python src/check_queue.py
   ```

3. **Download and upload to YouTube**
   - Manually via YouTube Studio or via API

4. **Mark as uploaded**
   ```bash
   python src/mark_uploaded.py <rhyme_id>
   ```

## 🔧 Configuration

Edit `config.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=...
PEXELS_API_KEY=...
DAILY_JOB_TIME=06:00
VIDEOS_PER_DAY=5
```

## 💾 GDrive Integration (Phase 2)

Next phase: automatically sync videos to Google Drive for scheduling from anywhere.

## 📝 See Also

- `SETUP.md` — Detailed setup instructions
- `docs/gdrive-integration.md` — Google Drive sync setup (coming soon)

