#!/usr/bin/env python3
"""Render slides.html into an animated MP4 with synthesized narration (macOS).

The deck exposes `seek(slide, ms)`, which freezes every CSS animation and JS-driven
state (count-ups, progress bar, slide cross-fade) at an exact time. For each slide we
screenshot the animated opening frame by frame at 25 fps, hold the last frame for the
rest of the narration, and mux the audio. Picture and voice are therefore aligned by
construction, with no screen recording involved.

Setup (once):  python3 -m pip install playwright && python3 -m playwright install chromium
Usage (from this directory):
    python3 build_video.py --dry-run          # word counts and estimated length
    python3 build_video.py                    # writes Group_34_Video.mp4
    python3 build_video.py --only 17          # one slide, for a quick look
    python3 build_video.py --voice Daniel --rate 160
"""
import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPS = 25
ANIM_MS = 3600      # animated opening of every slide that is rendered frame by frame
LEAD_SECONDS = 0.6  # silence before the voice starts, while the slide fades in
PAD_SECONDS = 0.9   # silence after the voice ends


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed ({r.returncode}): {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def narrations(html_path):
    text = html_path.read_text(encoding="utf-8")
    notes = re.findall(r'<aside class="notes">(.*?)</aside>', text, flags=re.S)
    return [re.sub(r"\s+", " ", html.unescape(n)).strip() for n in notes]


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(path)]).strip())


def render_frames(page, k, frames_dir):
    """Screenshot slide k at 0, 40, 80, ... ms; return the list of frame paths."""
    paths = []
    for j, t in enumerate(range(0, ANIM_MS + 1, 1000 // FPS)):
        page.evaluate(f"seek({k},{t})")
        f = frames_dir / f"s{k:02d}_{j:03d}.jpg"
        page.screenshot(path=str(f), type="jpeg", quality=93)
        paths.append(f)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Samantha")
    ap.add_argument("--rate", type=int, default=165, help="words per minute for `say`")
    ap.add_argument("--out", default="Group_34_Video.mp4")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", type=int, help="build a single slide (debug)")
    args = ap.parse_args()

    notes = narrations(HERE / "slides.html")
    words = [len(n.split()) for n in notes]
    est = sum(words) / args.rate + len(notes) * (LEAD_SECONDS + PAD_SECONDS) / 60
    print(f"{len(notes)} slides, {sum(words)} words, ~{est:.1f} min at {args.rate} wpm")
    if args.dry_run:
        for k, w in enumerate(words, 1):
            print(f"  slide {k:2d}: {w:4d} words")
        return
    for tool in ("ffmpeg", "ffprobe", "say"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} not found")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright missing: python3 -m pip install playwright && python3 -m playwright install chromium")

    build = HERE / "build"
    frames_dir = build / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    todo = [k for k in range(1, len(notes) + 1) if not args.only or k in (args.only - 1, args.only)]

    segments, timings, t0 = [], [], 0.0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"file://{HERE / 'slides.html'}?slide={todo[0]}")
        page.wait_for_timeout(500)   # fonts and images
        for k in todo:
            frames = render_frames(page, k, frames_dir)   # also sets up the cross-fade from k-1
            if args.only and k != args.only:
                continue
            aiff, seg, lst = build / f"slide_{k:02d}.aiff", build / f"seg_{k:02d}.mp4", build / f"frames_{k:02d}.txt"
            run(["say", "-v", args.voice, "-r", str(args.rate), "-o", str(aiff), notes[k - 1]])
            d = LEAD_SECONDS + duration(aiff) + PAD_SECONDS
            hold = max(d - (len(frames) - 1) / FPS, 1 / FPS)
            lines = [f"file '{f.resolve()}'\nduration {1 / FPS:.4f}\n" for f in frames[:-1]]
            lines.append(f"file '{frames[-1].resolve()}'\nduration {hold:.4f}\nfile '{frames[-1].resolve()}'\n")
            lst.write_text("".join(lines))
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                 "-i", str(aiff), "-t", f"{d:.3f}",
                 "-af", f"adelay={int(LEAD_SECONDS * 1000)}:all=1,apad",
                 "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                 "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(seg)])
            segments.append(seg)
            timings.append((k, t0, d))
            t0 += d
            print(f"  slide {k:2d}: {d:6.1f}s  (cum {t0 / 60:5.1f} min)", flush=True)
        browser.close()
    if errors:
        sys.exit("page errors while rendering: " + "; ".join(errors[:3]))

    lst = build / "segments.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segments))
    out = HERE / args.out
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    if not args.only:
        (HERE / "chapters.csv").write_text("slide,start_seconds,duration_seconds\n" +
                                           "".join(f"{k},{s:.1f},{d:.1f}\n" for k, s, d in timings))
        (HERE / "narration.txt").write_text("\n\n".join(f"[{k}] {n}" for k, n in enumerate(notes, 1)))
    print(f"wrote {out} ({duration(out) / 60:.1f} min)")


if __name__ == "__main__":
    main()
