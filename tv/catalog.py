"""Read-only episode discovery and library auditing."""

from dataclasses import dataclass
from pathlib import Path
import re


VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4"}

# Production episode counts for seasons 1-10. Together they total 226.
EXPECTED_EPISODES = {
    1: 13,
    2: 22,
    3: 24,
    4: 22,
    5: 22,
    6: 25,
    7: 25,
    8: 25,
    9: 25,
    10: 23,
}

EPISODE_ID_PATTERN = re.compile(
    r"(?:^|[^A-Z0-9])S(?P<season>\d{1,2})E(?P<episode>\d{1,2})(?=$|[^0-9])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Episode:
    """An episode recognized from a local video filename."""

    episode_id: str
    season: int
    episode: int
    title: str
    path: Path


@dataclass(frozen=True)
class CatalogReport:
    """The complete, read-only result of scanning one media directory."""

    root: Path
    episodes: tuple
    missing_ids: tuple
    duplicate_ids: tuple
    unexpected_ids: tuple
    unrecognized_paths: tuple

    @property
    def unique_episode_count(self):
        found = {episode.episode_id for episode in self.episodes}
        return len(found.intersection(expected_episode_ids()))

    @property
    def expected_episode_count(self):
        return sum(EXPECTED_EPISODES.values())

    @property
    def is_complete(self):
        return not (
            self.missing_ids
            or self.duplicate_ids
            or self.unexpected_ids
            or self.unrecognized_paths
        )


def normalize_episode_id(season, episode):
    """Return an episode ID such as ``S03E01``."""
    return "S%02dE%02d" % (season, episode)


def expected_episode_ids():
    """Return all expected season 1-10 episode IDs in broadcast order."""
    return tuple(
        normalize_episode_id(season, episode)
        for season, episode_count in sorted(EXPECTED_EPISODES.items())
        for episode in range(1, episode_count + 1)
    )


def parse_episode(path):
    """Parse an episode from *path*, or return ``None`` if no ID is present."""
    path = Path(path)
    match = EPISODE_ID_PATTERN.search(path.stem)
    if match is None:
        return None

    season = int(match.group("season"))
    episode = int(match.group("episode"))
    title = path.stem[match.end() :].lstrip(" -_.")

    return Episode(
        episode_id=normalize_episode_id(season, episode),
        season=season,
        episode=episode,
        title=title,
        path=path,
    )


def scan_library(root):
    """Scan *root* without changing it and return a :class:`CatalogReport`."""
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Video library does not exist or is not a directory: %s" % root)

    episodes = []
    unrecognized_paths = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            continue

        parsed = parse_episode(path)
        if parsed is None:
            unrecognized_paths.append(path)
        else:
            episodes.append(parsed)

    by_id = {}
    for episode in episodes:
        by_id.setdefault(episode.episode_id, []).append(episode)

    expected = set(expected_episode_ids())
    found = set(by_id)
    duplicate_ids = tuple(sorted(key for key, value in by_id.items() if len(value) > 1))

    return CatalogReport(
        root=root,
        episodes=tuple(episodes),
        missing_ids=tuple(sorted(expected - found)),
        duplicate_ids=duplicate_ids,
        unexpected_ids=tuple(sorted(found - expected)),
        unrecognized_paths=tuple(unrecognized_paths),
    )


def format_report(report):
    """Render a concise human-readable audit report."""
    lines = [
        "Simpsons TV library audit",
        "Library: %s" % report.root,
        "Video files recognized: %d" % len(report.episodes),
        "Unique expected episodes: %d / %d"
        % (report.unique_episode_count, report.expected_episode_count),
    ]

    _append_list(lines, "Missing", report.missing_ids)
    _append_list(lines, "Duplicate IDs", report.duplicate_ids)
    _append_list(lines, "Unexpected IDs", report.unexpected_ids)

    if report.unrecognized_paths:
        relative_paths = tuple(
            str(path.relative_to(report.root)) for path in report.unrecognized_paths
        )
        _append_list(lines, "Unrecognized video filenames", relative_paths)
    else:
        lines.append("Unrecognized video filenames: none")

    lines.append("Status: %s" % ("COMPLETE" if report.is_complete else "NEEDS ATTENTION"))
    return "\n".join(lines)


def _append_list(lines, label, values):
    if values:
        lines.append("%s (%d): %s" % (label, len(values), ", ".join(values)))
    else:
        lines.append("%s: none" % label)

