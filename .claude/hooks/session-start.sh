#!/bin/bash
set -euo pipefail

# Only run in Claude Code on the web (remote container) sessions.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

echo "[session-start] Installing Python dependencies..."
pip install -q -r requirements.txt --ignore-installed PyYAML

# Locate a Chromium binary. The remote containers ship a Playwright-bundled
# Chromium under /opt/pw-browsers; pick the newest one.
CHROME_BINARY=""
if [ -d /opt/pw-browsers ]; then
  CHROME_BINARY="$(ls -1d /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | sort -V | tail -n1 || true)"
fi

if [ -z "$CHROME_BINARY" ] || [ ! -x "$CHROME_BINARY" ]; then
  echo "[session-start] No usable Chromium binary found under /opt/pw-browsers — skipping Selenium setup."
  exit 0
fi

CHROME_VERSION="$("$CHROME_BINARY" --version 2>/dev/null | awk '{print $2}')"
CHROME_MAJOR_MINOR_BUILD="$(echo "$CHROME_VERSION" | cut -d. -f1-3)"
echo "[session-start] Found Chromium $CHROME_VERSION at $CHROME_BINARY"

DRIVER_DIR="$HOME/.cache/mcmp-chromedriver/$CHROME_VERSION"
DRIVER_BIN="$DRIVER_DIR/chromedriver-linux64/chromedriver"

if [ ! -x "$DRIVER_BIN" ]; then
  echo "[session-start] Resolving matching chromedriver for $CHROME_VERSION..."
  DRIVER_URL="$(python3 - <<PY
import json, sys, urllib.request
url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
data = json.loads(urllib.request.urlopen(url, timeout=30).read())
prefix = "$CHROME_MAJOR_MINOR_BUILD."
matches = [v for v in data["versions"] if v["version"].startswith(prefix) or v["version"] == "$CHROME_VERSION"]
if not matches:
    major = "$CHROME_VERSION".split(".")[0] + "."
    matches = [v for v in data["versions"] if v["version"].startswith(major)]
if not matches:
    sys.exit("no chromedriver match")
chosen = matches[-1]
for d in chosen["downloads"].get("chromedriver", []):
    if d["platform"] == "linux64":
        print(d["url"])
        break
PY
)"
  if [ -z "$DRIVER_URL" ]; then
    echo "[session-start] No matching chromedriver download URL — skipping."
    exit 0
  fi
  mkdir -p "$DRIVER_DIR"
  curl -sSL -o "$DRIVER_DIR/driver.zip" "$DRIVER_URL"
  (cd "$DRIVER_DIR" && unzip -oq driver.zip && rm driver.zip)
  chmod +x "$DRIVER_BIN"
fi

echo "[session-start] chromedriver: $("$DRIVER_BIN" --version)"

{
  echo "export MCMP_CHROME_BINARY=\"$CHROME_BINARY\""
  echo "export MCMP_CHROMEDRIVER=\"$DRIVER_BIN\""
} >> "$CLAUDE_ENV_FILE"

echo "[session-start] Done."
