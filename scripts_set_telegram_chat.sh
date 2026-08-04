#!/usr/bin/env bash
# Finish wiring this project's Telegram notifications.
#
# Telegram will not let a bot message you until you have started a conversation
# with it, so this cannot be done unattended:
#
#   1. Open Telegram, search for @aiNurseryRhymesBot
#   2. Press Start (or send it any message)
#   3. Run this script
#
# It reads the chat id from the bot's pending updates and writes it into
# config.env. The token is never printed.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

set -a; . ./config.env; set +a
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN missing from config.env}"

CHAT="$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" | python3 -c '
import sys, json
d = json.load(sys.stdin)
for u in reversed(d.get("result", [])):
    c = (u.get("message") or u.get("channel_post") or {}).get("chat", {})
    if c.get("id"):
        print(c["id"]); break
')"

if [ -z "$CHAT" ]; then
  echo "No chat found. Send any message to @aiNurseryRhymesBot first, then re-run." >&2
  exit 1
fi

python3 - "$CHAT" <<'PY'
import pathlib, re, sys
chat = sys.argv[1]
p = pathlib.Path("config.env")
lines, done = [], False
for ln in p.read_text().splitlines(keepends=True):
    if re.match(r'^\s*TELEGRAM_CHAT_ID\s*=', ln):
        lines.append(f"TELEGRAM_CHAT_ID={chat}\n"); done = True
    else:
        lines.append(ln)
if not done:
    lines.append(f"TELEGRAM_CHAT_ID={chat}\n")
p.write_text("".join(lines))
print(f"wrote TELEGRAM_CHAT_ID={chat} to config.env")
PY

set -a; . ./config.env; set +a
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" -d "parse_mode=HTML" \
  --data-urlencode "text=<b>🤖 ai-nursery-rhymes notifications live</b>
Autonomous repair for the video pipeline will report here. The trading bot reports elsewhere." \
  | python3 -c "import sys,json;print('delivered:', json.load(sys.stdin).get('ok'))"
