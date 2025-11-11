# GoodLifeToM3U8

Auto-generates a stable playlist for **The Good Life Radio** by refreshing the YouTube HLS URL on a schedule.

## Files
- `streams.txt`
- `grabber.py`
- `exec_grabber.sh`
- `.github/workflows/linkgrabber.yml`

## After pushing to GitHub
- Run **Actions → LinkGrabber → Run workflow**
- Your raw URLs (replace `serevis` if different):
  - M3U8: https://raw.githubusercontent.com/serevis/GoodLifeToM3U8/main/streams.m3u8
  - EPG:  https://raw.githubusercontent.com/serevis/GoodLifeToM3U8/main/epg.xml
