#!/usr/bin/env python3
"""
Watches the Event Cinemas IMAX Sydney "now showing" page for The Odyssey.
Sends a free push notification (via ntfy.sh) whenever a NEW session id
shows up — which is how new session dates/times get added to the page.
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

PAGE_URL = "https://www.eventcinemas.com.au/cinema/imax-sydney/nowshowing"
# On your PC, this hardcoded value is used. On GitHub Actions, the
# NTFY_TOPIC secret (passed in as an environment variable) overrides it.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "CHANGE-ME-to-a-private-topic-name")
STATE_FILE = Path(__file__).parent / "odyssey_imax_state.json"


def fetch_odyssey_session_ids():
    resp = requests.get(
        PAGE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; personal-session-watcher/1.0)"},
        timeout=20,
    )
    resp.raise_for_status()
    html = resp.text

    start = html.find("The Odyssey")
    if start == -1:
        print("Could not find 'The Odyssey' section — page layout may have changed.")
        return set()
    end = html.find("Our Cinemas", start)
    block = html[start: end if end != -1 else start + 8000]

    return set(re.findall(r"sessionId=(\d+)", block))


def send_ntfy_alert(new_ids):
    title = "New Odyssey IMAX Sydney sessions"
    message = f"{len(new_ids)} new session(s) just appeared. Check times & book:\n{PAGE_URL}"
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "movie_camera"},
        timeout=10,
    )


def main():
    if NTFY_TOPIC.startswith("CHANGE-ME"):
        sys.exit("Set NTFY_TOPIC (env var or hardcoded) to a private topic name before running.")

    current_ids = fetch_odyssey_session_ids()
    if not current_ids:
        return

    if STATE_FILE.exists():
        previous_ids = set(json.loads(STATE_FILE.read_text()))
        new_ids = current_ids - previous_ids
        if new_ids:
            print(f"New session ids found: {new_ids}")
            send_ntfy_alert(new_ids)
        else:
            print("No new sessions.")
    else:
        print("First run — establishing baseline, no alert sent.")

    STATE_FILE.write_text(json.dumps(sorted(current_ids)))


if __name__ == "__main__":
    main()
