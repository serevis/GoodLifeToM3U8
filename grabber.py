#!/usr/bin/env python3
import subprocess, shlex, sys, json
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE = Path(__file__).resolve().parent

def parse_streams_txt(path: Path):
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    entries = []
    # Expect pairs: meta line + URL line
    for i in range(0, len(lines), 2):
        meta = lines[i]
        url  = lines[i+1] if i+1 < len(lines) else ""
        parts = [p.strip() for p in meta.split("||")]
        if len(parts) != 3:
            print(f"[warn] Skipping malformed entry: {meta}", file=sys.stderr)
            continue
        name, chan_id, category = parts
        entries.append({"name": name, "id": chan_id, "category": category, "url": url})
    return entries

def _run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True).strip()

def get_stream_url_with_ytdlp(url: str) -> str:
    """
    Try multiple strategies to get a playable HLS (.m3u8) URL for YouTube Live.
    """
    # 1) Fast path: direct URL(s) via -g (may return 1–2 lines)
    candidates = [
        'best[protocol^=m3u8]',                 # explicit HLS
        'bv*+ba/b[protocol^=m3u8]/b',           # merge or best HLS
        'best'                                  # anything (last-resort)
    ]
    for fmt in candidates:
        cmd = f"yt-dlp --no-warnings -g -f {shlex.quote(fmt)} {shlex.quote(url)}"
        try:
            out = _run(cmd)
            if not out:
                continue
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            # Prefer an .m3u8 line if present; otherwise last line
            for ln in lines:
                if ".m3u8" in ln or "protocol=hls" in ln or "m3u8" in ln:
                    return ln
            return lines[-1]
        except subprocess.CalledProcessError as e:
            # Try the next strategy
            continue

    # 2) JSON probe: parse formats and pick protocol=m3u8 / ext=m3u8
    try:
        j = _run(f"yt-dlp -J {shlex.quote(url)}")
        data = json.loads(j)
        fmts = data.get("formats") or []
        # Sort by quality preference, keep HLS only
        hls = [f for f in fmts if (f.get("protocol") or "").startswith("m3u8") or "m3u8" in (f.get("ext") or "")]
        # Prefer video+audio variants, then highest tbr
        hls.sort(key=lambda f: (0 if f.get("vcodec") not in (None, "none") else 1, f.get("tbr") or 0), reverse=True)
        for f in hls:
            u = f.get("url") or f.get("manifest_url")
            if u:
                return u
    except Exception as e:
        pass

    return ""  # let caller handle

def write_m3u8(entries, out_path: Path):
    lines = ["#EXTM3U"]
    for e in entries:
        resolved = e.get("resolved_url") or ""
        if not resolved:
            # Keep broken entries out of the final playlist to avoid player errors
            print(f"[error] No playable URL for: {e['name']}", file=sys.stderr)
            continue
        name = e["name"].replace("\n", " ").strip()
        cat  = e["category"].strip()
        cid  = e["id"].strip()
        # Minimal but TiviMate-friendly tags
        lines.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" group-title="{cat}",{name}')
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
        print("[fatal] streams.txt not found", file=sys.stderr); sys.exit(1)
    entries = parse_streams_txt(streams_file)
    if not entries:
        print("[fatal] No valid entries found in streams.txt", file=sys.stderr); sys.exit(1)

    any_ok = False
    for e in entries:
        url = e["url"]
        if not url:
            print(f"[warn] Missing URL for: {e['name']}", file=sys.stderr)
            continue
        resolved = get_stream_url_with_ytdlp(url)
        if resolved:
            e["resolved_url"] = resolved
            any_ok = True
            print(f"[info] {e['name']} -> HLS OK")
        else:
            print(f"[error] Could not resolve HLS for: {e['name']}", file=sys.stderr)

    write_m3u8(entries, BASE / "streams.m3u8")
    write_epg(entries, BASE / "epg.xml")

    if not any_ok:
        print("[fatal] No channels produced playable HLS. See logs above.", file=sys.stderr)
        sys.exit(2)

    print("Generated streams.m3u8 and epg.xml")

if __name__ == "__main__":
    main()
