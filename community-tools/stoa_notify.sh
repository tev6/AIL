#!/usr/bin/env bash
# stoa_notify.sh — pipe stoa_receiver.ail output through this to get
# macOS desktop notifications on each incoming letter.
#
# Usage:
#   PORT=8765 ail run community-tools/stoa_receiver.ail \
#     | community-tools/stoa_notify.sh
#
# Each letter is buffered between "=== stoa letter ===" markers; we
# extract from/title and pop a notification.
#
# Author: Ergon — 2026-04-27 (v1.61.0 Phase B)

if ! command -v osascript >/dev/null 2>&1; then
  echo "[stoa_notify] osascript not found — passing through" >&2
  cat
  exit 0
fi

from=""
title=""
in_letter=0

while IFS= read -r line; do
  echo "$line"
  case "$line" in
    "=== stoa letter ===")
      in_letter=1
      from=""; title=""
      ;;
    "===================")
      if [ "$in_letter" = "1" ]; then
        # Strip newlines and quotes for AppleScript safety
        msg="${title:-(no title)}"
        sender="${from:-stoa}"
        osascript -e "display notification \"${msg//\"/\'}\" with title \"Stoa: ${sender//\"/\'}\"" >/dev/null 2>&1 || true
      fi
      in_letter=0
      ;;
    from:*)
      [ "$in_letter" = "1" ] && from="${line#from:  }"
      ;;
    title:*)
      [ "$in_letter" = "1" ] && title="${line#title:  }"
      ;;
  esac
done
