#!/usr/bin/env python3
import sys
import json
from upload_queue import UploadQueue

def main():
    if len(sys.argv) < 2:
        print("Usage: python mark_uploaded.py <rhyme_id> [youtube_long_id] [youtube_short_id]")
        print("\nExample:")
        print("  python mark_uploaded.py twinkle_star dQw4w9WgXcQ dQw4w9WgXcR")
        sys.exit(1)

    rhyme_id = sys.argv[1]
    youtube_long_id = sys.argv[2] if len(sys.argv) > 2 else None
    youtube_short_id = sys.argv[3] if len(sys.argv) > 3 else None

    queue = UploadQueue(queue_file="./upload_queue.json")
    youtube_ids = {}
    if youtube_long_id:
        youtube_ids["long"] = youtube_long_id
    if youtube_short_id:
        youtube_ids["short"] = youtube_short_id

    try:
        queue.mark_uploaded(rhyme_id, youtube_ids if youtube_ids else None)
        print(f"\n✓ Marked as uploaded: {rhyme_id}")
        if youtube_ids:
            print(f"   YouTube IDs: {youtube_ids}")
        print()
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
