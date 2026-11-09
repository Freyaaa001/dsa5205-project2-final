#!/usr/bin/env python3
"""Render slides.html into an MP4 with synthesized narration (macOS only).

Pipeline per slide: headless Chrome screenshot (1920x1080) -> `say` narration from the
slide's <aside class="notes"> -> ffmpeg still-image segment; segments are concatenated.

Usage (from this directory):
    python3 build_video.py                 # default voice Samantha, rate 165 wpm
    python3 build_video.py --voice Daniel --rate 160 --out Group_34_Video.mp4
    python3 build_video.py --dry-run       # word counts and estimated length only
"""
import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAD_SECONDS = 1.2   # silence appended after each slide's narration


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"command failed ({r.returncode}): {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def narrations(html_path):
    text = html_path.read_text(encoding="utf-8")
    notes = re.findall(r'<aside class="notes">(.*?)</aside>', text, flags=re.S)
    return [re.sub(r"\s+", " ", html.unescape(n)).strip() for n in notes]


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.strip())


def screenshot(index, out_png):
    url = f"file://{HERE / 'slides.html'}?slide={index}"
    run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
         "--force-device-scale-factor=1", "--window-size=1920,1080",
         "--virtual-time-budget=4000", f"--screenshot={out_png}", url])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Samantha")
    ap.add_argument("--rate", type=int, default=165, help="words per minute for `say`")
    ap.add_argument("--out", default="Group_34_Video.mp4")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", type=int, help="build a single slide segment (debug)")
    args = ap.parse_args()

    notes = narrations(HERE / "slides.html")
    words = [len(n.split()) for n in notes]
    print(f"{len(notes)} slides, {sum(words)} words, ~{sum(words)/args.rate + len(notes)*PAD_SECONDS/60:.1f} min at {args.rate} wpm")
    if args.dry_run:
        for k, w in enumerate(words, 1):
            print(f"  slide {k:2d}: {w:4d} words")
        return
    for tool in ("ffmpeg", "ffprobe", "say"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} not found")
    if not Path(CHROME).exists():
        sys.exit("Google Chrome not found at " + CHROME)

    build = HERE / "build"
    build.mkdir(exist_ok=True)
    segments, timings, t0 = [], [], 0.0
    for k, text in enumerate(notes, 1):
        if args.only and k != args.only:
            continue
        png, aiff, seg = build / f"slide_{k:02d}.png", build / f"slide_{k:02d}.aiff", build / f"seg_{k:02d}.mp4"
        screenshot(k, png)
        run(["say", "-v", args.voice, "-r", str(args.rate), "-o", str(aiff), text])
        d = duration(aiff) + PAD_SECONDS
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "1", "-i", str(png),
             "-i", str(aiff), "-t", f"{d:.3f}", "-af", "apad", "-r", "25", "-c:v", "libx264",
             "-preset", "ultrafast", "-tune", "stillimage", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(seg)])
        segments.append(seg)
        timings.append((k, t0, d))
        t0 += d
        print(f"  slide {k:2d}: {d:6.1f}s  (cum {t0/60:5.1f} min)")

    lst = build / "segments.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segments))
    out = HERE / args.out
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    (HERE / "chapters.csv").write_text("slide,start_seconds,duration_seconds\n" +
                                       "".join(f"{k},{s:.1f},{d:.1f}\n" for k, s, d in timings))
    (HERE / "narration.txt").write_text("\n\n".join(f"[{k}] {n}" for k, n in enumerate(notes, 1)))
    print(f"wrote {out} ({duration(out)/60:.1f} min)")


if __name__ == "__main__":
    main()
