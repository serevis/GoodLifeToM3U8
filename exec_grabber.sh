#!/usr/bin/env bash
set -euo pipefail
python3 grabber.py
echo "Wrote streams.m3u8 and epg.xml"
