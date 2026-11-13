#!/usr/bin/env python3
"""Transcribe commercial reels and add conservative review evidence to manifests."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPOSITORY_ROOT / "commercials" / "v2"
DEFAULT_CLI = Path(
    "/Users/meierjo/Canna/Training Courses/.transcription/venv/bin/mlx_whisper"
)
DEFAULT_MODEL = Path(
    "/Users/meierjo/Canna/Training Courses/.transcription/models/whisper-large-v3-turbo"
)
PIPELINE_VERSION = 1
SILENCE_PATTERN = re.compile(
    r"silence_start:\s*(?P<start>\d+(?:\.\d+)?)|"
    r"silence_end:\s*(?P<end>\d+(?:\.\d+)?)"
)
SPONSOR_PATTERNS = (
    "brought to you by",
    "sponsored by",
    "is brought to you",
    "has been brought to you",
)
CREDITS_PATTERNS = (
    "executive producer",
    "co-executive producer",
    "supervising producer",
    "associate producer",
    "produced by",
    "written by",
    "directed by",
    "created by",
    "casting by",
    "all rights reserved",
    "copyright",
)
PROMO_PATTERNS = (
    "tonight on",
    "next on",
    "on the next",
    "season premiere",
    "series premiere",
    "game break",
    "around the league",
    "right after",
    "tomorrow at",
    "coming up next",
    "we'll be right back",
    "we will be right back",
    "stay tuned",
)
AD_PATTERNS = (
    "call now",
    "available at",
    "participating locations",
    "participating restaurants",
    "limited time",
    "suggested retail",
    "ask your doctor",
    "visit us",
    "buy one",
    "free with",
    "only $",
)
LEADING_FRAGMENT_PATTERN = re.compile(
    r"^(?:and|but|because|so|then|which|that|or|also)\b", re.IGNORECASE
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="Transcribe commercial reels and recommend strict Keep choices."
    )
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        dest="years",
        help="analyze only this year; repeat for a multi-year batch",
    )
    parser.add_argument("--manifest", type=Path, help="analyze one manifest")
    parser.add_argument("--cli", type=Path, default=DEFAULT_CLI)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--apply-strict", action="store_true")
    parser.add_argument("--skip-transcription", action="store_true")
    return parser.parse_args(argv)


def manifest_paths(root, years=None, manifest=None):
    if manifest is not None:
        return (Path(manifest).expanduser().resolve(),)
    paths = sorted((Path(root).expanduser().resolve() / "manifests").glob("*.json"))
    if not years:
        return tuple(paths)
    prefixes = tuple("%d-" % year for year in years)
    return tuple(path for path in paths if path.name.startswith(prefixes))


def raw_transcript_path(root, manifest_path):
    return Path(root).resolve() / "analysis" / "raw" / (manifest_path.stem + ".json")


def readable_transcript_paths(root, manifest_path):
    base = Path(root).resolve() / "analysis" / "transcripts" / manifest_path.stem
    return base.with_suffix(".txt"), base.with_suffix(".vtt")


def transcribe_reel(source, raw_path, cli, model):
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.is_file():
        return False
    if not Path(cli).is_file():
        raise RuntimeError("mlx-whisper CLI not found: %s" % cli)
    if not Path(model).exists():
        raise RuntimeError("Whisper model not found: %s" % model)
    output_name = raw_path.stem + ".working"
    working_path = raw_path.parent / (output_name + ".json")
    prompt = (
        "American television commercials and network continuity from 1989 through 1999. "
        "Common phrases include The Simpsons, FOX, brought to you by, sponsored by, "
        "we'll be right back, executive producer, and copyright notices."
    )
    command = [
        str(cli), str(source),
        "--model", str(model),
        "--output-dir", str(raw_path.parent),
        "--output-name", output_name,
        "--output-format", "json",
        "--language", "en",
        "--word-timestamps", "True",
        "--condition-on-previous-text", "False",
        "--verbose", "False",
        "--initial-prompt", prompt,
    ]
    subprocess.run(command, check=True)
    # mlx-whisper 0.4.3 may treat the final dotted component of output-name
    # like a suffix and write directly to raw_path instead of working_path.
    if raw_path.is_file():
        return True
    if not working_path.is_file():
        raise RuntimeError("mlx-whisper did not produce %s" % working_path)
    os.replace(str(working_path), str(raw_path))
    return True


def parse_silences(output):
    intervals = []
    start = None
    for match in SILENCE_PATTERN.finditer(output):
        if match.group("start") is not None:
            start = float(match.group("start"))
        elif match.group("end") is not None and start is not None:
            intervals.append((start, float(match.group("end"))))
            start = None
    return tuple(intervals)


def detect_silences(source):
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", str(source),
            "-af", "silencedetect=noise=-38dB:d=0.12",
            "-vn", "-f", "null", "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("FFmpeg silence analysis failed: %s" % result.stderr[-1200:])
    return parse_silences(result.stderr)


def timed_units(data):
    words = []
    for segment in data.get("segments", []):
        if float(segment.get("compression_ratio") or 0) > 3.0:
            continue
        words.extend(segment.get("words") or [])
    usable_words = [
        {
            "start": float(word.get("start", 0)),
            "end": float(word.get("end", word.get("start", 0))),
            "text": str(word.get("word", word.get("text", ""))).strip(),
        }
        for word in words
        if str(word.get("word", word.get("text", ""))).strip()
    ]
    if usable_words:
        return usable_words, "word"
    segments = []
    for segment in data.get("segments", []):
        text = str(segment.get("text") or "").strip()
        if text and float(segment.get("compression_ratio") or 0) <= 3.0:
            segments.append(
                {
                    "start": float(segment.get("start", 0)),
                    "end": float(segment.get("end", segment.get("start", 0))),
                    "text": text,
                }
            )
    return segments, "segment"


def interval_near(point, intervals, tolerance=0.16):
    return any(start - tolerance <= point <= end + tolerance for start, end in intervals)


def close_to_standard_duration(duration):
    standards = ((10, 1.5), (15, 2.5), (20, 2.0), (30, 2.5), (45, 2.5), (60, 3.0))
    return any(abs(duration - target) <= tolerance for target, tolerance in standards)


def phrase_hits(text, patterns):
    lowered = text.casefold()
    return [phrase for phrase in patterns if phrase in lowered]


def classify_clip(
    clip, units, timing_mode, silences, source_duration=None, manually_excluded=False
):
    start = float(clip["start"])
    end = float(clip["end"])
    duration = float(clip.get("duration", end - start))
    overlapping = [unit for unit in units if unit["end"] > start and unit["start"] < end]
    text = " ".join(unit["text"] for unit in overlapping).strip()
    first_speech = min((unit["start"] for unit in overlapping), default=None)
    last_speech = max((unit["end"] for unit in overlapping), default=None)
    crosses_start = any(
        unit["start"] < start - 0.05 and unit["end"] > start + 0.05 for unit in units
    )
    crosses_end = any(
        unit["start"] < end - 0.05 and unit["end"] > end + 0.05 for unit in units
    )
    sponsor_hits = phrase_hits(text, SPONSOR_PATTERNS)
    credits_hits = phrase_hits(text, CREDITS_PATTERNS)
    promo_hits = phrase_hits(text, PROMO_PATTERNS)
    ad_hits = phrase_hits(text, AD_PATTERNS)
    clean_start = start <= 0.15 or interval_near(start, silences)
    clean_end = (
        (source_duration is not None and end >= source_duration - 0.15)
        or interval_near(end, silences)
    )
    reasons = []
    if sponsor_hits:
        reasons.append("Sponsor wording: %s" % ", ".join(sponsor_hits))
    if credits_hits:
        reasons.append("Credits wording: %s" % ", ".join(credits_hits))
    if promo_hits:
        reasons.append("Program-continuity wording: %s" % ", ".join(promo_hits))
    if crosses_start:
        reasons.append("Speech crosses the start cut")
    if crosses_end:
        reasons.append("Speech crosses the end cut")
    if text and LEADING_FRAGMENT_PATTERN.match(text):
        reasons.append("Transcript begins like a continuation")
    if text.strip(" .!?").casefold() == "the end":
        credits_hits.append("the end")
        reasons.append("End-title wording")
    if manually_excluded:
        reasons.append("File is in the committed manual exclusion list")

    suggested_kind = "uncertain"
    recommended = False
    confidence = 0.45
    if manually_excluded:
        suggested_kind = "manually-excluded"
        confidence = 1.0
    elif credits_hits:
        suggested_kind = "credits"
        confidence = min(0.99, 0.72 + 0.07 * len(credits_hits))
    elif promo_hits:
        suggested_kind = "program-continuity"
        confidence = min(0.96, 0.72 + 0.06 * len(promo_hits))
    elif crosses_start or crosses_end:
        suggested_kind = "suspected-fragment"
        confidence = 0.91
    elif duration > 35.0:
        suggested_kind = "long-form-candidate"
        confidence = 0.82
        reasons.append("Over 35 seconds; reviewed reels commonly contain multiple spots")
    elif sponsor_hits:
        suggested_kind = "sponsor-bumper"
        recommended = clean_start and clean_end
        confidence = 0.96 if recommended else 0.78
    elif 0 < len(text.split()) < 4:
        suggested_kind = "uncertain"
        confidence = 0.62
        reasons.append("Too little speech evidence for automatic approval")
    elif text and close_to_standard_duration(duration) and clean_start and clean_end:
        suggested_kind = "commercial"
        recommended = True
        confidence = min(0.94, 0.76 + 0.03 * len(ad_hits))
    elif text and close_to_standard_duration(duration) and (clean_start or clean_end):
        suggested_kind = "commercial-candidate"
        confidence = min(0.82, 0.62 + 0.03 * len(ad_hits))
    elif not text:
        reasons.append("No reliable speech transcript; visual review required")

    return {
        "pipeline_version": PIPELINE_VERSION,
        "timing_mode": timing_mode,
        "transcript": text,
        "suggested_kind": suggested_kind,
        "recommended_approved": recommended,
        "confidence": round(confidence, 2),
        "speech_start": None if first_speech is None else round(max(0, first_speech - start), 3),
        "speech_end": None if last_speech is None else round(min(duration, last_speech - start), 3),
        "crosses_start": crosses_start,
        "crosses_end": crosses_end,
        "clean_start": clean_start,
        "clean_end": clean_end,
        "reasons": reasons,
    }


def timestamp(seconds):
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return "%02d:%02d:%02d.%03d" % (hours, minutes, seconds, milliseconds)


def write_readable_transcripts(root, manifest_path, units):
    txt_path, vtt_path = readable_transcript_paths(root, manifest_path)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(" ".join(unit["text"] for unit in units).strip() + "\n")
    lines = ["WEBVTT", ""]
    for number, unit in enumerate(units, 1):
        lines.extend(
            [str(number), "%s --> %s" % (timestamp(unit["start"]), timestamp(unit["end"])), unit["text"], ""]
        )
    vtt_path.write_text("\n".join(lines))


def atomic_write_json(path, payload):
    temporary = Path(path).with_suffix(Path(path).suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(str(temporary), str(path))


def load_manual_exclusions():
    path = REPOSITORY_ROOT / "config" / "commercials.json"
    if not path.is_file():
        return set()
    with path.open() as config_file:
        config = json.load(config_file)
    return {Path(str(item)).as_posix() for item in config.get("excluded_files", [])}


def analyze_manifest(root, manifest_path, cli, model, skip_transcription=False, apply_strict=False):
    with Path(manifest_path).open() as manifest_file:
        manifest = json.load(manifest_file)
    source = Path(manifest["source_file"]).expanduser()
    if not source.is_file():
        raise RuntimeError("Source reel not found: %s" % source)
    raw_path = raw_transcript_path(root, manifest_path)
    if not skip_transcription:
        transcribe_reel(source, raw_path, cli, model)
    if not raw_path.is_file():
        raise RuntimeError("Raw transcript not found: %s" % raw_path)
    with raw_path.open() as raw_file:
        transcript = json.load(raw_file)
    units, timing_mode = timed_units(transcript)
    if not units:
        raise RuntimeError("Transcript contains no usable timed speech: %s" % raw_path)
    silences = detect_silences(source)
    source_duration = max((float(clip["end"]) for clip in manifest["clips"]), default=None)
    kept_before = sum(bool(clip.get("approved")) for clip in manifest["clips"])
    recommended = 0
    changed = 0
    manual_exclusions = load_manual_exclusions()
    for clip in manifest["clips"]:
        analysis = classify_clip(
            clip,
            units,
            timing_mode,
            silences,
            source_duration,
            Path(str(clip.get("file", ""))).as_posix() in manual_exclusions,
        )
        clip["analysis"] = analysis
        if analysis["recommended_approved"]:
            recommended += 1
        if apply_strict and clip.get("approved") and not analysis["recommended_approved"]:
            clip["approved"] = False
            changed += 1
    manifest["analysis"] = {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": utc_now(),
        "model": str(model),
        "raw_transcript": str(raw_path.relative_to(Path(root).resolve())),
        "timing_mode": timing_mode,
        "silence_intervals": len(silences),
        "mode": "apply-strict" if apply_strict else "recommend",
    }
    if apply_strict:
        manifest["status"] = (
            "approved" if all(clip.get("approved") for clip in manifest["clips"])
            else "needs-review"
        )
    atomic_write_json(manifest_path, manifest)
    write_readable_transcripts(root, manifest_path, units)
    return {
        "clips": len(manifest["clips"]),
        "kept_before": kept_before,
        "recommended": recommended,
        "unchecked": changed,
        "timing_mode": timing_mode,
    }


def run(args):
    root = args.root.expanduser().resolve()
    paths = manifest_paths(root, args.years, args.manifest)
    if not paths:
        raise RuntimeError("No matching commercial manifests found")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required")
    failures = 0
    for number, path in enumerate(paths, 1):
        print("[%d/%d] %s" % (number, len(paths), path.name), flush=True)
        try:
            result = analyze_manifest(
                root, path, args.cli.expanduser(), args.model.expanduser(),
                args.skip_transcription, args.apply_strict,
            )
            print(
                "  %d clips; %d recommended; %d unchecked; %s timing"
                % (result["clips"], result["recommended"], result["unchecked"], result["timing_mode"]),
                flush=True,
            )
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
            failures += 1
            print("  ERROR: %s" % error, file=sys.stderr, flush=True)
    return 1 if failures else 0


def main(argv=None):
    try:
        return run(parse_arguments(argv))
    except RuntimeError as error:
        print("Commercial analysis failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
