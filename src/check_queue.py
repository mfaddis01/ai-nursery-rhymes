#!/usr/bin/env python3
import json
from pathlib import Path
import sys
from datetime import datetime
from upload_queue import UploadQueue

def format_queue_display(queue_summary: dict) -> str:
    """Format queue summary as readable output."""
    output = []
    output.append("\n" + "=" * 70)
    output.append("📺 UPLOAD QUEUE STATUS")
    output.append("=" * 70)
    output.append(f"\n📊 Summary:")
    output.append(f"   Total videos in queue: {queue_summary['total_in_queue']}")
    output.append(f"   Pending upload: {queue_summary['pending_videos']}")
    output.append(f"\n🎬 Pending Videos ({queue_summary['pending_videos']} entries):\n")

    pending = queue_summary['pending_entries']
    if not pending:
        output.append("   (no videos pending)\n")
    else:
        for i, entry in enumerate(pending, 1):
            date = entry['created_at'][:10]
            title = entry['title']
            output.append(f"   {i}. [{date}] {title}")
            output.append(f"      ID: {entry['rhyme_id']}")
            output.append(f"      Theme: {', '.join(entry.get('theme', []))}")
            output.append(f"      Status: {entry['status']}")
            output.append(f"      Long:  {Path(entry['long_video_path']).name}")
            output.append(f"      Short: {Path(entry['short_video_path']).name}")
            output.append("")

    output.append("=" * 70)
    output.append("\n💡 Next steps:")
    output.append("   1. Download the video files (see paths above)")
    output.append("   2. Upload to YouTube manually or use YouTube API")
    output.append("   3. Run: python mark_uploaded.py <rhyme_id>\n")
    return "\n".join(output)

if __name__ == "__main__":
    try:
        queue = UploadQueue(queue_file="./upload_queue.json")
        summary = queue.get_queue_summary()
        print(format_queue_display(summary))
    except FileNotFoundError:
        print("\n❌ Error: upload_queue.json not found")
        print("   Run the scheduler first to generate videos\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)
