"""Canonical episode filenames shared by encoding and migration tools."""

from pathlib import Path
import re

from tv.catalog import parse_episode


WHITESPACE = re.compile(r"\s+")


def clean_title(title):
    """Return a filesystem-safe title without changing normal punctuation."""
    title = WHITESPACE.sub(" ", title).strip(" .")
    return title.replace("/", "-").replace("\x00", "")


def canonical_episode_filename(path, metadata=None, suffix=".mp4"):
    """Return ``SxxExx - Title.mp4`` or ``None`` for an unrecognized path."""
    episode = parse_episode(path)
    if episode is None:
        return None

    metadata = metadata or {}
    title = metadata.get(episode.episode_id, {}).get("title") or episode.title
    title = clean_title(title)
    if not title:
        raise ValueError("Episode has no usable title: %s" % Path(path).name)
    return "%s - %s%s" % (episode.episode_id, title, suffix.lower())

