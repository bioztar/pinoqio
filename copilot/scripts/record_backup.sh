#!/usr/bin/env bash
# Record the backup demo video: the Pinoqio desktop window ONLY, replaying the demo call, with the call audio muxed in.
#   copilot/scripts/record_backup.sh            (macOS, unlocked, screen recording allowed for the terminal)
# Env: PINOQIO_ENV_FILE (keys, default <repo>/.env)  DURATION (s, default 150)
#      STARTUP_LAG (s from launch to replay start, default 1.2; tune if audio is early/late)  AUDIO_OFFSET (s, overrides the estimate)
# Output: copilot/demo/backup-demo.mp4 (H.264 + AAC) and 3 stills in $STILLS (default: a temp dir) to eyeball that only the window is in frame.
set -euo pipefail

COPILOT="$(cd "$(dirname "$0")/.." && pwd)"
REPLAY="$COPILOT/demo/replay"
OUT="$COPILOT/demo/backup-demo.mp4"
DURATION="${DURATION:-150}"
STARTUP_LAG="${STARTUP_LAG:-1.2}"
WORK="$(mktemp -d)"
STILLS="${STILLS:-$WORK}"
export PINOQIO_ENV_FILE="${PINOQIO_ENV_FILE:-$COPILOT/../.env}"
export PINOQIO_WHISPER_DEVICE="MacBook Air Speakers" PINOQIO_PUBLIC_DEVICE="MacBook Air Speakers"
PY=(uv run --no-project --with pyobjc-framework-Quartz python)

# a locked screen records the lock window, not the app
"${PY[@]}" - <<'EOF'
import sys, Quartz
if Quartz.CGSessionCopyCurrentDictionary().get("CGSSessionScreenIsLocked"):
    sys.exit("screen is locked: unlock the Mac first")
EOF

cd "$COPILOT"
uv run python -m pinoqio.app --source replay --them-wav "$REPLAY/them.wav" --me-wav "$REPLAY/me.wav" > "$WORK/app.log" 2>&1 &
APP_UV=$!
trap 'pkill -P "$APP_UV" 2>/dev/null || true; kill "$APP_UV" 2>/dev/null || true' EXIT
T_LAUNCH=$(python3 -c 'import time; print(time.time())')

# window bounds by owning PID (the python child of `uv run`), once they stop moving; crop in capture pixels on the right display
until APP_PID=$(pgrep -f "$COPILOT/.venv/bin/python3 -m pinoqio.app" | head -1) && [ -n "$APP_PID" ]; do sleep 0.2; done
CROP=$("${PY[@]}" - "$APP_PID" <<'EOF'
import sys, time, Quartz
pid = int(sys.argv[1])

def find():
    for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
        b = w["kCGWindowBounds"]
        if w.get("kCGWindowOwnerPID") == pid and w.get("kCGWindowName") == "Pinoqio" and b["Width"] > 100:
            return (b["X"], b["Y"], b["Width"], b["Height"])

prev, deadline = None, time.time() + 40
while time.time() < deadline:
    cur = find()
    if cur and cur == prev:
        break
    prev = cur
    time.sleep(0.4)
else:
    sys.exit("Pinoqio window not found")
x, y, w, h = cur
_, ids, _ = Quartz.CGGetActiveDisplayList(8, None, None)
for ordinal, d in enumerate(ids):  # avfoundation lists "Capture screen N" in this order
    r = Quartz.CGDisplayBounds(d)
    if r.origin.x <= x < r.origin.x + r.size.width and r.origin.y <= y < r.origin.y + r.size.height:
        s = Quartz.CGDisplayModeGetPixelWidth(Quartz.CGDisplayCopyDisplayMode(d)) / r.size.width
        even = lambda v: int(round(v * s)) // 2 * 2
        print(ordinal, even(w), even(h), int(round((x - r.origin.x) * s)), int(round((y - r.origin.y) * s)))
        sys.exit(0)
sys.exit("window is on no active display")
EOF
)
read -r ORDINAL CW CH CX CY <<< "$CROP"
FIRST=$(ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 | sed -n 's/.*\[\([0-9]*\)\] Capture screen 0.*/\1/p' | head -1)
SCREEN=$(( FIRST + ORDINAL ))
echo "window ${CW}x${CH} at +${CX}+${CY} on screen index $SCREEN"

RAW="$WORK/raw.mp4"
T_REC=$(python3 -c 'import time; print(time.time())')
ffmpeg -y -loglevel error -f avfoundation -framerate 30 -capture_cursor 0 -i "$SCREEN:none" -t "$DURATION" \
  -vf "crop=$CW:$CH:$CX:$CY" -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$RAW"

# audio plays from replay start (~launch + STARTUP_LAG); video starts at T_REC. Positive: delay audio, negative: trim it.
OFFSET="${AUDIO_OFFSET:-$(python3 -c "print(round($T_LAUNCH + $STARTUP_LAG - $T_REC, 3))")}"
echo "audio offset ${OFFSET}s"
if python3 -c "import sys; sys.exit(0 if $OFFSET >= 0 else 1)"; then AIN=(-itsoffset "$OFFSET" -i "$REPLAY/call.mp3"); else AIN=(-ss "${OFFSET#-}" -i "$REPLAY/call.mp3"); fi
ffmpeg -y -loglevel error -i "$RAW" "${AIN[@]}" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 128k -shortest "$OUT"

for t in 20 75 140; do ffmpeg -y -loglevel error -ss "$t" -i "$OUT" -frames:v 1 "$STILLS/still$t.png"; done
SIZE=$(stat -f %z "$OUT")
echo "wrote $OUT ($((SIZE / 1024)) KB); stills in $STILLS (check only the Pinoqio window is in frame)"
[ "$SIZE" -le $((40 * 1024 * 1024)) ] || echo "WARNING: over 40 MB, do not commit; keep it untracked"
