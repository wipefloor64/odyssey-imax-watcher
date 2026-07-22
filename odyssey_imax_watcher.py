#!/usr/bin/env python3
"""
Watches the Event Cinemas IMAX Sydney "now showing" page for The Odyssey.
Sends a free push notification (via ntfy.sh) whenever a NEW session id
shows up — which is how new session dates/times get added to the page.

Known limitation: the page does not expose a date label in the content
this script can read (dates are shown via a JS-rendered day selector).
So alerts include the SESSION TIME (e.g. "6:15 AM") but not the date.
The time is matched to its session id by text position on the page —
this is a best-effort pairing, not a guaranteed structural one, so if
Event Cinemas changes their page layout this could mismatch or fail;
check the log output if something looks off.
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

PAGE_URL = "https://www.eventcinemas.com.au/cinema/imax-sydney/nowshowing"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "lawrence-odyssey-9f3k2")
STATE_FILE = Path(__file__).parent / "odyssey_imax_state.json"


def fetch_odyssey_sessions():
    """Returns a dict of {session_id: time_string_or_None} for The Odyssey."""
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
        return {}
    end = html.find("Our Cinemas", start)
    block = html[start: end if end != -1 else start + 8000]

    # Best-effort: grab a time like "9:30 PM" followed (within ~300 chars)
    # by a sessionId. If the site's layout shifts, this may return None
    # for the time — the id-diffing logic still works either way.
    sessions = {}
    for match in re.finditer(r"sessionId=(\d+)", block):
        session_id = match.group(1)
        preceding_text = block[max(0, match.start() - 300): match.start()]
        time_match = re.findall(r"\d{1,2}:\d{2}\s?[AaPp][Mm]", preceding_text)
        sessions[session_id] = time_match[-1] if time_match else None

    return sessions


def send_ntfy_alert(new_sessions):
    title = "New Odyssey IMAX Sydney sessions"
    lines = []
    for session_id, time_str in new_sessions.items():
        lines.append(f"- {time_str or 'time unknown'} (id {session_id})")
    message = (
        f"{len(new_sessions)} new session(s) just appeared:\n"
        + "\n".join(lines)
        + f"\n\nDate isn't available from this page — check & book:\n{PAGE_URL}"
    )
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "movie_camera"},
        timeout=10,
    )


def main():
    if NTFY_TOPIC.startswith("CHANGE-ME"):
        sys.exit("Set NTFY_TOPIC (env var or hardcoded) to a private topic name before running.")

    current_sessions = fetch_odyssey_sessions()
    if not current_sessions:
        return

    if STATE_FILE.exists():
        previous_ids = set(json.loads(STATE_FILE.read_text()))
        new_ids = set(current_sessions) - previous_ids
        if new_ids:
            new_sessions = {sid: current_sessions[sid] for sid in new_ids}
            print(f"New sessions found: {new_sessions}")
            send_ntfy_alert(new_sessions)
        else:
            print("No new sessions.")
    else:
        print("First run — establishing baseline, no alert sent.")

    STATE_FILE.write_text(json.dumps(sorted(current_sessions)))


if __name__ == "__main__":
    main()
