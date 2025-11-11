#!/usr/bin/env python3
import subprocess, shlex, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE = Path(__file__).resolve().parent

def parse_streams_txt(path: Path):
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    entries = []
    for i in range(0, len(lines), 2):
        meta = lines[i]
        url  = lines[i+1] if i+1 < len(lines) else ""
        parts = [p.strip() for p in meta.split("||")]
        if len(parts) != 3:
            print(f"Skipping malformed entry: {meta}", file=sys.stderr)
            continue
        name, chan_id, category = parts
        entries.append({"name": name, "id": chan_id, "category": category, "url": url})
    return entries

def get_stream_url_with_ytdlp(url: str) -> str:
    candidates = ['best[protocol^=m3u8]','bv*+ba/b[protocol^=m3u8]/b','best[ext=mp4]','best']
    for fmt in candidates:
        cmd = f"yt-dlp --no-warnings -g -f {shlex.quote(fmt)} {shlex.quote(url)}"
        try:
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True).strip()
            if out:
                return out.splitlines()[-1].strip()
        except subprocess.CalledProcessError:
            continue
    return ""

def write_m3u8(entries, out_path: Path):
    lines = ["#EXTM3U"]
    for e in entries:
        resolved = e.get("resolved_url") or e.get("url")
        name = e["name"].replace("\n", " ").strip()
        cat  = e["category"].strip()
        cid  = e["id"].strip()
        lines.append(f'#EXTINF:-1 tvg-id="{cid}" group-title="{cat}",{name}')
        lines.append(resolved)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def write_epg(entries, out_path: Path):
    now = datetime.now(timezone.utc)
    stop = now + timedelta(hours=24)
    def fmt(dt): return dt.strftime("%Y%m%d%H%M%S +0000")
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="GoodLifeToM3U8">']
    for e in entries:
        cid = e["id"].strip()
        name = e["name"].strip()
        parts.append(f'  <channel id="{cid}">')
        parts.append(f'    <display-name>{name}</display-name>')
        parts.append(f'  </channel>')
        parts.append(f'  <programme start="{fmt(now)}" stop="{fmt(stop)}" channel="{cid}">')
        parts.append(f'    <title>{name} (Live)</title>')
        parts.append(f'    <desc>Auto-generated EPG slot for a continuous live stream.</desc>')
        parts.append(f'  </programme>')
    parts.append('</tv>')
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")

def main():
    streams_file = BASE / "streams.txt"
    if not streams_file.exists():
        print("streams.txt not found", file=sys.stderr); sys.exit(1)
    entries = parse_streams_txt(streams_file)
    if not entries:
        print("No valid entries found in streams.txt", file=sys.stderr); sys.exit(1)
    for e in entries:
        url = e["url"]
        if not url: continue
        resolved = get_stream_url_with_ytdlp(url)
        e["resolved_url"] = resolved or url
    write_m3u8(entries, BASE / "streams.m3u8")
    write_epg(entries, BASE / "epg.xml")
    print("Generated streams.m3u8 and epg.xml")

if __name__ == "__main__":
    main()
