# Quick GDrive Setup on WSL

## One-Command Setup

```bash
cd ~/ai-nursery-rhymes
bash setup_gdrive_interactive.sh
```

This script will:
1. Install Google Cloud CLI
2. Create a Google Cloud project
3. Create a service account
4. Enable Google Drive API
5. Create the Drive folder
6. Auto-configure your project

## What You Need

- Google account
- Internet connection (for OAuth)
- 5-10 minutes

## After Setup

1. Edit `config.env` and add your API keys:
   ```
   ANTHROPIC_API_KEY=...
   ELEVENLABS_API_KEY=...
   PEXELS_API_KEY=...
   ```

2. Test:
   ```bash
   cd src
   python daily_scheduler.py test
   ```

3. Deploy:
   ```bash
   python daily_scheduler.py &
   ```

Videos will automatically sync to your Google Drive folder!

