#!/usr/bin/env python3
"""Download, split, encode, and inventory a reel of vintage commercials."""

import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_CATALOG = REPOSITORY_ROOT / "commercials" / "sources.json"
BLACK_INTERVAL_PATTERN = re.compile(
    r"black_start:(?P<start>\d+(?:\.\d+)?)\s+"
    r"black_end:(?P<end>\d+(?:\.\d+)?)"
)
TARGET_DURATIONS = (
    (10.0, 0.0),
    (15.0, 0.0),
    (20.0, 0.0),
    (30.0, 0.0),
    (45.0, 0.15),
    (60.0, 0.25),
)
DURATION_PATTERN = re.compile(
    r"Duration:\s*(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+(?:\.\d+)?)"
)
SCENE_TIME_PATTERN = re.compile(r"pts_time:(?P<time>\d+(?:\.\d+)?)")


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="Turn a commercial-break reel into reviewable Pi-ready clips."
    )
    parser.add_argument("--year", type=valid_year, required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="already-downloaded reel")
    source.add_argument("--url", help="public reel URL to download with yt-dlp")
    parser.add_argument(
        "--source-number",
        type=int,
        default=1,
        help="1-based saved source for the year when --input/--url is omitted",
    )
    parser.add_argument("--output-root", type=Path, default=REPOSITORY_ROOT / "commercials")
    parser.add_argument("--min-seconds", type=float, default=8.0)
    parser.add_argument("--max-seconds", type=float, default=75.0)
    parser.add_argument(
        "--dry-run", action="store_true", help="detect and report cuts without encoding"
    )
    return parser.parse_args(argv)


def valid_year(value):
    try:
        year = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("year must be a number")
    if not 1980 <= year <= 2030:
        raise argparse.ArgumentTypeError("year must be between 1980 and 2030")
    return year


def load_saved_source(path, year, source_number=1):
    with Path(path).open() as source_file:
        sources = json.load(source_file).get("sources", [])
    matches = [source for source in sources if source.get("year") == year]
    if not 1 <= source_number <= len(matches):
        raise ValueError(
            "Year %s has %d saved source(s); requested source %d"
            % (year, len(matches), source_number)
        )
    return matches[source_number - 1]


def parse_black_intervals(output):
    return tuple(
        (float(match.group("start")), float(match.group("end")))
        for match in BLACK_INTERVAL_PATTERN.finditer(output)
    )


def parse_scene_points(output):
    return tuple(float(match.group("time")) for match in SCENE_TIME_PATTERN.finditer(output))


def choose_segments(
    duration, black_intervals, minimum=8.0, maximum=75.0, segment_penalty=0.0
):
    """Choose plausible ad segments using black-screen midpoints as cut points."""
    if duration <= 0:
        raise ValueError("Reel duration must be positive")
    if minimum <= 0 or maximum <= minimum:
        raise ValueError("Invalid commercial duration range")

    boundaries = [0.0]
    boundaries.extend((start + end) / 2.0 for start, end in black_intervals)
    boundaries.append(float(duration))
    boundaries = sorted(set(round(point, 3) for point in boundaries))

    # Dynamic programming avoids splitting on every internal black frame. The
    # preferred path uses intervals near common 10/15/20/30/45/60-second ads.
    best = {0: (0.0, [])}
    # Discard a short slate, station bumper, or partial ad before the first
    # detected boundary instead of gluing it onto the first real commercial.
    for index, boundary in enumerate(boundaries[1:], 1):
        if boundary > minimum:
            break
        best[index] = (0.0, [])
    last_index = len(boundaries) - 1
    for end_index in range(1, len(boundaries)):
        for start_index in range(end_index):
            if start_index not in best:
                continue
            segment_duration = boundaries[end_index] - boundaries[start_index]
            edge_fragment = start_index == 0 or end_index == last_index
            if segment_duration > maximum:
                continue
            if segment_duration < minimum and not edge_fragment:
                continue
            cost = min(
                (abs(segment_duration - target) / 5.0) ** 2 + penalty
                for target, penalty in TARGET_DURATIONS
            ) + segment_penalty
            if segment_duration < minimum:
                cost += 25.0
            previous_cost, previous_segments = best[start_index]
            candidate = (
                previous_cost + cost,
                previous_segments
                + [(boundaries[start_index], boundaries[end_index])],
            )
            if end_index not in best or (
                candidate[0], -len(candidate[1])
            ) < (
                best[end_index][0], -len(best[end_index][1])
            ):
                best[end_index] = candidate

    endings = []
    for index, candidate in best.items():
        trailing_fragment = duration - boundaries[index]
        if index == last_index or trailing_fragment <= minimum:
            endings.append(candidate)
    if not endings:
        raise ValueError(
            "No plausible cuts found. Try a larger --max-seconds value or split the reel first."
        )
    selected = min(endings, key=lambda candidate: (candidate[0], -len(candidate[1])))
    return tuple(selected[1])


def parse_duration(output):
    match = DURATION_PATTERN.search(output)
    if match is None:
        raise ValueError("FFmpeg did not report a media duration")
    return (
        int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + float(match.group("seconds"))
    )


def probe_duration(path):
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return parse_duration(result.stderr)


def detect_black_intervals(path):
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            # VHS captures often have only three or four near-black frames
            # between spots. A short duration and slightly tolerant pixel
            # threshold catches those without forcing every detection to be a
            # cut; choose_segments still rejects implausibly tiny fragments.
            "blackdetect=d=0.10:pix_th=0.15",
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("FFmpeg analysis failed:\n%s" % result.stderr[-2000:])
    return parse_black_intervals(result.stderr)


def detect_scene_points(path):
    """Return only very strong hard cuts for reels without black separators."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            "select='gt(scene,0.60)',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("FFmpeg scene analysis failed:\n%s" % result.stderr[-2000:])
    return parse_scene_points(result.stderr)


def download_reel(url, incoming_directory):
    incoming_directory.mkdir(parents=True, exist_ok=True)
    template = str(incoming_directory / "%(title).120B [%(id)s].%(ext)s")
    subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--restrict-filenames",
            "--merge-output-format",
            "mp4",
            "-o",
            template,
            "--print",
            "after_move:filepath",
            url,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    # Resolve from the directory instead of trusting downloader stdout across
    # yt-dlp versions and post-processing output formats.
    candidates = sorted(
        (path for path in incoming_directory.glob("*") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise RuntimeError("yt-dlp completed without producing a media file")
    return candidates[-1]


def encode_clip(source, destination, start, end):
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "%.3f" % start,
            "-i",
            str(source),
            "-t",
            "%.3f" % (end - start),
            "-vf",
            "scale=-2:480",
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        check=True,
    )


def safe_stem(path):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", Path(path).stem).strip("-").lower()
    return cleaned[:60] or "commercial-reel"


def write_manifest(path, output_root, year, source_path, source_url, segments, clips):
    payload = {
        "year": year,
        "source_file": str(source_path),
        "source_url": source_url,
        "status": "needs-review",
        "clips": [
            {
                "file": str(clip.relative_to(output_root)),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "approved": False,
            }
            for (start, end), clip in zip(segments, clips)
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_review_page(path, year, manifest_path, clips, segments):
    cards = []
    for number, (clip, (start, end)) in enumerate(zip(clips, segments), 1):
        relative_clip = Path(os.path.relpath(clip, path.parent))
        cards.append(
            "<article><h2>Clip %03d</h2>"
            "<video controls preload='metadata' src='%s'></video>"
            "<p>%.1f–%.1f seconds · %.1f seconds</p>"
            "<label><input type='checkbox'> Keep</label></article>"
            % (number, html.escape(str(relative_clip)), start, end, end - start)
        )
    document = """<!doctype html>
<html><head><meta charset="utf-8"><title>%s commercial review</title>
<style>body{font:16px system-ui;background:#171527;color:#fff;margin:2rem}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}
article{background:#292545;padding:1rem;border-radius:12px}video{width:100%%}
small{color:#c9c3e8}</style></head><body>
<h1>%s commercial candidates</h1>
<p><small>Review the clips, then update approved flags in %s. Checkboxes are a
temporary visual aid and do not modify files.</small></p><main>%s</main></body></html>
""" % (year, year, html.escape(manifest_path.name), "".join(cards))
    path.write_text(document)


def write_review_index(directory):
    pages = sorted(Path(directory).glob("*-review.html"))
    links = "".join(
        "<li><a href='%s'>%s</a></li>"
        % (html.escape(page.name), html.escape(page.stem.replace("-review", "")))
        for page in pages
    )
    document = """<!doctype html><html><head><meta charset="utf-8">
<title>Commercial import reviews</title>
<style>body{font:18px system-ui;background:#171527;color:#fff;max-width:900px;
margin:3rem auto;padding:0 1rem}a{color:#ffd54a}li{margin:.8rem 0}</style>
</head><body><h1>Commercial import reviews</h1><ol>%s</ol></body></html>
""" % links
    index_path = Path(directory) / "index.html"
    index_path.write_text(document)
    return index_path


def require_programs(programs):
    missing = [program for program in programs if shutil.which(program) is None]
    if missing:
        raise RuntimeError("Missing required program(s): %s" % ", ".join(missing))


def run(args):
    source_url = args.url
    if args.input is None and source_url is None:
        saved = load_saved_source(DEFAULT_SOURCE_CATALOG, args.year, args.source_number)
        source_url = saved["url"]

    required = ["ffmpeg"]
    if args.input is None:
        required.append("yt-dlp")
    require_programs(required)

    output_root = args.output_root.expanduser().resolve()
    if args.input is not None:
        source_path = args.input.expanduser().resolve()
        if not source_path.is_file():
            raise ValueError("Input reel does not exist: %s" % source_path)
    else:
        source_path = download_reel(source_url, output_root / "incoming")

    duration = probe_duration(source_path)
    black_intervals = detect_black_intervals(source_path)
    scene_points = ()
    try:
        segments = choose_segments(
            duration, black_intervals, args.min_seconds, args.max_seconds
        )
    except ValueError:
        scene_points = detect_scene_points(source_path)
        combined_intervals = tuple(black_intervals) + tuple(
            (point, point) for point in scene_points
        )
        segments = choose_segments(
            duration,
            combined_intervals,
            args.min_seconds,
            args.max_seconds,
            segment_penalty=0.22,
        )
    stem = safe_stem(source_path)
    clip_directory = output_root / str(args.year) / stem
    clips = tuple(
        clip_directory / ("%d - %s - %03d.mp4" % (args.year, stem, number))
        for number in range(1, len(segments) + 1)
    )

    print(
        "Detected %d black transition(s)%s; planned %d candidate clip(s)."
        % (
            len(black_intervals),
            " plus %d strong scene cut(s)" % len(scene_points) if scene_points else "",
            len(segments),
        )
    )
    for number, (start, end) in enumerate(segments, 1):
        print("%03d  %8.3f - %8.3f  (%5.1fs)" % (number, start, end, end - start))
    if args.dry_run:
        return 0

    for clip, (start, end) in zip(clips, segments):
        encode_clip(source_path, clip, start, end)

    manifest_directory = output_root / "manifests"
    manifest_path = manifest_directory / ("%d-%s.json" % (args.year, stem))
    review_path = manifest_directory / ("%d-%s-review.html" % (args.year, stem))
    write_manifest(
        manifest_path,
        output_root,
        args.year,
        source_path,
        source_url,
        segments,
        clips,
    )
    write_review_page(review_path, args.year, manifest_path, clips, segments)
    review_index = write_review_index(manifest_directory)
    print("Manifest: %s" % manifest_path)
    print("Review page: %s" % review_path)
    print("Review index: %s" % review_index)
    return 0


def main(argv=None):
    try:
        return run(parse_arguments(argv))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print("Commercial import failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
