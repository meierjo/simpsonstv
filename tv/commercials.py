"""Approved commercial discovery and period-correct preroll selection."""

from dataclasses import dataclass
import json
from pathlib import Path
import random


@dataclass(frozen=True)
class CommercialClip:
    """One reviewed local commercial or sponsor bumper."""

    path: Path
    year: int
    kind: str = "commercial"


def load_broadcast_years(path):
    """Load compact season/episode broadcast-year cutovers."""
    path = Path(path)
    try:
        with path.open() as year_file:
            data = json.load(year_file)
    except (OSError, ValueError) as error:
        raise ValueError("Could not load broadcast years from %s: %s" % (path, error))

    seasons = data.get("seasons")
    if not isinstance(seasons, dict):
        raise ValueError("Broadcast-year configuration must contain seasons")

    rules = {}
    for season, cutovers in seasons.items():
        try:
            season_number = int(season)
            parsed = tuple((int(last_episode), int(year)) for last_episode, year in cutovers)
        except (TypeError, ValueError):
            raise ValueError("Invalid broadcast-year rules for season %s" % season)
        if not parsed or any(parsed[index][0] <= parsed[index - 1][0] for index in range(1, len(parsed))):
            raise ValueError("Broadcast-year cutovers must be ordered for season %s" % season)
        rules[season_number] = parsed
    return rules


def broadcast_year_for_episode(episode, metadata, rules):
    """Return an episode's original US broadcast year, or ``None``."""
    episode_metadata = metadata.get(episode.episode_id, {})
    explicit_year = episode_metadata.get("air_year")
    if explicit_year is not None:
        return int(explicit_year)
    air_date = episode_metadata.get("air_date")
    if isinstance(air_date, str) and len(air_date) >= 4 and air_date[:4].isdigit():
        return int(air_date[:4])

    for last_episode, year in rules.get(episode.season, ()):
        if episode.episode <= last_episode:
            return year
    return None


def load_approved_clips(root, excluded_files=()):
    """Read approved, existing clips from importer manifests below *root*."""
    root = Path(root).expanduser().resolve()
    excluded = {Path(str(path)).as_posix() for path in excluded_files}
    clips = []
    seen_paths = set()
    for manifest_path in sorted(root.glob("manifests/*.json")):
        try:
            with manifest_path.open() as manifest_file:
                manifest = json.load(manifest_file)
            year = int(manifest["year"])
            records = manifest["clips"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict) or not record.get("approved"):
                continue
            relative_path = record.get("file")
            if not isinstance(relative_path, str):
                continue
            clip_path = (root / relative_path).resolve()
            try:
                relative_path = clip_path.relative_to(root).as_posix()
            except ValueError:
                continue
            if (
                relative_path in excluded
                or not clip_path.is_file()
                or clip_path in seen_paths
            ):
                continue
            clips.append(CommercialClip(clip_path, year, record.get("kind", "commercial")))
            seen_paths.add(clip_path)
    return tuple(clips)


class CommercialScheduler:
    """Choose exact-year preroll while avoiding recent commercial repeats."""

    def __init__(self, clips, recent_limit=12, random_source=None, include_bumpers=True):
        self._clips = tuple(clips)
        self._recent_limit = max(0, int(recent_limit))
        self._random = random_source or random.Random()
        self._recent_paths = []
        self.include_bumpers = bool(include_bumpers)

    def choose_preroll(self, year):
        """Return at most one bumper and one commercial for *year*."""
        if year is None:
            return ()
        selected = []
        if self.include_bumpers:
            bumper = self._choose(year, {"sponsor-bumper"})
            if bumper is not None:
                selected.append(bumper)
        commercial_kinds = {clip.kind for clip in self._clips if clip.kind != "sponsor-bumper"}
        commercial = self._choose(year, commercial_kinds)
        if commercial is not None:
            selected.append(commercial)
        return tuple(selected)

    def _choose(self, year, kinds):
        candidates = [clip for clip in self._clips if clip.year == year and clip.kind in kinds]
        if not candidates:
            return None
        recent = set(self._recent_paths[-self._recent_limit :]) if self._recent_limit else set()
        fresh = [clip for clip in candidates if clip.path not in recent]
        selected = self._random.choice(fresh or candidates)
        self._recent_paths.append(selected.path)
        if self._recent_limit:
            self._recent_paths = self._recent_paths[-self._recent_limit :]
        else:
            self._recent_paths = []
        return selected
