#!/usr/bin/env python3
"""Propose post-opening commercial cues from chapters and audio fingerprints."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from tv.catalog import parse_episode  # noqa: E402


CHAPTER_PATTERN = re.compile(
    r"Chapter #0:0: start [\d.]+, end (?P<end>[\d.]+)"
)
FINGERPRINT_RATE = 8.0


def require_program(name):
    path = shutil.which(name)
    if path is None:
        raise ValueError("Required program is not installed: %s" % name)
    return path


def season_episodes(library, season):
    episodes = []
    for path in sorted(Path(library).expanduser().resolve().glob("*.mp4")):
        episode = parse_episode(path)
        if episode is not None and episode.season == season:
            episodes.append(episode)
    if not episodes:
        raise ValueError("No season %d episodes found in %s" % (season, library))
    return tuple(sorted(episodes, key=lambda episode: episode.episode))


def first_chapter_end(ffmpeg, path):
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    match = CHAPTER_PATTERN.search(result.stderr)
    return float(match.group("end")) if match else None


def fingerprint_episode(fpcalc, episode, cache_directory, length_seconds):
    cache_path = cache_directory / (episode.episode_id + ".json")
    stat = episode.path.stat()
    if cache_path.is_file():
        cached = json.loads(cache_path.read_text())
        if cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns:
            return cached
    result = subprocess.run(
        [
            fpcalc,
            "-raw",
            "-json",
            "-length",
            str(length_seconds),
            str(episode.path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    payload.update(
        {
            "episode_id": episode.episode_id,
            "path": str(episode.path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    )
    cache_path.write_text(json.dumps(payload))
    return payload


def fingerprint_similarity(left, right, seconds, threshold=10, jitter=2):
    """Compare aligned Chromaprint frames with small encode-time jitter."""
    frame_count = min(int(seconds * FINGERPRINT_RATE), len(left), len(right))
    if frame_count <= 0:
        return 0.0
    matching = 0
    for index in range(frame_count):
        start = max(0, index - jitter)
        end = min(len(right), index + jitter + 1)
        distance = min((left[index] ^ right[other]).bit_count() for other in range(start, end))
        if distance <= threshold:
            matching += 1
    return matching / float(frame_count)


def fingerprint_prefix_end(
    left,
    right,
    minimum_seconds=12.0,
    maximum_seconds=180.0,
    threshold=10,
    jitter=2,
):
    """Find where a strongly shared opening becomes sustained different audio."""
    frame_count = min(
        len(left), len(right), int(maximum_seconds * FINGERPRINT_RATE)
    )
    matches = []
    for index in range(frame_count):
        start = max(0, index - jitter)
        end = min(len(right), index + jitter + 1)
        distance = min(
            (left[index] ^ right[other]).bit_count() for other in range(start, end)
        )
        matches.append(distance <= threshold)
    future_frames = int(5.0 * FINGERPRINT_RATE)
    future_match_ceiling = 0.15
    for index in range(int(minimum_seconds * FINGERPRINT_RATE), frame_count - future_frames):
        prefix_score = sum(matches[:index]) / float(index)
        future_score = sum(matches[index : index + future_frames]) / float(
            future_frames
        )
        if prefix_score >= 0.65 and future_score <= future_match_ceiling:
            # The rolling window becomes eligible just before the actual
            # boundary because a small matching tail is allowed. Compensate
            # for that allowance when reporting the estimated cut point.
            correction = round(future_frames * future_match_ceiling)
            return (index + correction) / FINGERPRINT_RATE, prefix_score
    return None, 0.0


def choose_audio_prefix_candidate(rows, tolerance=6.0):
    """Choose the latest corroborated cluster, or the strongest lone peer."""
    if not rows:
        return None
    clusters = []
    for row in rows:
        cluster = [
            candidate
            for candidate in rows
            if abs(candidate[0] - row[0]) <= tolerance
        ]
        unique = {candidate[2]: candidate for candidate in cluster}
        cluster = list(unique.values())
        if len(cluster) >= 2:
            clusters.append(cluster)
    if clusters:
        # A longer opening only matches peers whose opening is at least as
        # long. Prefer the latest corroborated group, then stronger support.
        cluster = max(
            clusters,
            key=lambda values: (
                sorted(item[0] for item in values)[len(values) // 2],
                sum(item[1] for item in values) / len(values),
                len(values),
            ),
        )
    else:
        cluster = [max(rows, key=lambda row: (row[1], row[0]))]
    ends = sorted(row[0] for row in cluster)
    cue = ends[len(ends) // 2]
    best = max(cluster, key=lambda row: row[1])
    average_score = sum(row[1] for row in cluster) / len(cluster)
    return cue, average_score, len(cluster), best[2]


def analyze_candidates(episodes, fingerprints, chapter_ends, maximum_cue=180.0):
    candidates = {}
    for episode in episodes:
        chapter_cue = chapter_ends.get(episode.episode_id)
        cue = chapter_cue
        plausible = cue is not None and 10.0 <= cue <= maximum_cue
        peer_rows = []
        method = "chapter+audio" if plausible else "audio-prefix"
        if plausible:
            for peer in episodes:
                if peer.episode_id == episode.episode_id:
                    continue
                peer_cue = chapter_ends.get(peer.episode_id)
                if peer_cue is None or not 10.0 <= peer_cue <= maximum_cue:
                    continue
                score = fingerprint_similarity(
                    fingerprints[episode.episode_id],
                    fingerprints[peer.episode_id],
                    min(cue, peer_cue),
                )
                peer_rows.append((score, abs(cue - peer_cue), peer.episode_id, peer_cue))
            best = max(peer_rows, default=(0.0, 999.0, None, None))
            score, cue_delta, peer_id, peer_cue = best
            support_count = sum(
                row[0] >= 0.80 and row[1] <= 6.0 for row in peer_rows
            )
            if score >= 0.80 and cue_delta <= 6.0:
                confidence = "high"
            elif score >= 0.65:
                confidence = "medium"
            else:
                confidence = "low"
        else:
            prefix_rows = []
            for peer in episodes:
                if peer.episode_id == episode.episode_id:
                    continue
                prefix_end, prefix_score = fingerprint_prefix_end(
                    fingerprints[episode.episode_id], fingerprints[peer.episode_id]
                )
                if prefix_end is not None:
                    prefix_rows.append(
                        (prefix_end, prefix_score, peer.episode_id)
                    )
            selected = choose_audio_prefix_candidate(prefix_rows)
            if selected is None:
                cue = None
                score = 0.0
                support_count = 0
                peer_id = None
                peer_cue = None
                confidence = "low"
                method = "none"
            else:
                cue, score, support_count, peer_id = selected
                peer_cue = cue
                confidence = (
                    "high"
                    if support_count >= 2 and score >= 0.80
                    else "medium"
                )
        candidates[episode.episode_id] = {
            "episode_id": episode.episode_id,
            "title": episode.title,
            "source_file": str(episode.path),
            "intro_start": 0.0,
            "intro_end": round(cue, 3) if cue is not None else None,
            "chapter_end": (
                round(chapter_cue, 3) if chapter_cue is not None else None
            ),
            "confidence": confidence,
            "best_peer": peer_id,
            "best_peer_intro_end": round(peer_cue, 3) if peer_cue is not None else None,
            "audio_similarity": round(score, 4),
            "audio_peer_count": support_count,
            "detection_method": method,
            "reviewed": False,
        }
    return candidates


def encode_preview(ffmpeg, source, destination, start, duration=5.0):
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "%.3f" % max(0.0, start),
            "-i",
            str(source),
            "-t",
            "%.3f" % duration,
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            str(destination),
        ],
        check=True,
    )


def build_previews(ffmpeg, output_directory, candidates, workers=4):
    preview_directory = output_directory / "previews"
    jobs = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for episode_id, candidate in candidates.items():
            cue = candidate["intro_end"]
            if cue is None:
                continue
            source = Path(candidate["source_file"])
            before = preview_directory / (episode_id + "-before.mp4")
            after = preview_directory / (episode_id + "-after.mp4")
            candidate["preview_before"] = str(before.relative_to(output_directory))
            candidate["preview_after"] = str(after.relative_to(output_directory))
            jobs.append(pool.submit(encode_preview, ffmpeg, source, before, cue - 5.0))
            jobs.append(pool.submit(encode_preview, ffmpeg, source, after, cue))
        for job in as_completed(jobs):
            job.result()


def run(args):
    fpcalc = require_program("fpcalc")
    ffmpeg = require_program("ffmpeg")
    episodes = season_episodes(args.library, args.season)
    output_directory = args.output.expanduser().resolve()
    cache_directory = output_directory / "cache"
    cache_directory.mkdir(parents=True, exist_ok=True)

    fingerprint_payloads = {}
    chapter_ends = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fingerprint_jobs = {
            pool.submit(
                fingerprint_episode,
                fpcalc,
                episode,
                cache_directory,
                args.length_seconds,
            ): episode
            for episode in episodes
        }
        chapter_jobs = {
            pool.submit(first_chapter_end, ffmpeg, episode.path): episode
            for episode in episodes
        }
        for job, episode in fingerprint_jobs.items():
            fingerprint_payloads[episode.episode_id] = job.result()
        for job, episode in chapter_jobs.items():
            chapter_ends[episode.episode_id] = job.result()

    fingerprints = {
        episode_id: payload["fingerprint"]
        for episode_id, payload in fingerprint_payloads.items()
    }
    candidates = analyze_candidates(episodes, fingerprints, chapter_ends)
    if not args.no_previews:
        build_previews(ffmpeg, output_directory, candidates, workers=args.workers)
    payload = {
        "schema_version": 1,
        "season": args.season,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "library": str(Path(args.library).expanduser().resolve()),
        "episodes": candidates,
    }
    output_path = output_directory / ("season-%02d-candidates.json" % args.season)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    counts = {
        confidence: sum(item["confidence"] == confidence for item in candidates.values())
        for confidence in ("high", "medium", "low")
    }
    print("Analyzed %d season %d episodes: %s" % (len(episodes), args.season, counts))
    print("Candidates: %s" % output_path)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--output", type=Path, default=REPOSITORY_ROOT / "analysis" / "intros"
    )
    parser.add_argument("--length-seconds", type=int, default=180)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--no-previews", action="store_true")
    return parser


def main(argv=None):
    try:
        return run(build_parser().parse_args(argv))
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print("Intro analysis failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
