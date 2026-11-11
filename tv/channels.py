"""Data-driven channel definitions and episode filtering."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Channel:
    """A named view of the episode catalog."""

    channel_id: str
    name: str
    required_tags: tuple


def load_episode_metadata(path):
    """Load episode metadata keyed by normalized episode ID."""
    data = _load_json(path)
    episodes = data.get("episodes")
    if not isinstance(episodes, dict):
        raise ValueError("Episode metadata must contain an 'episodes' object")
    return episodes


def load_channels(path):
    """Load channel definitions keyed by channel ID."""
    data = _load_json(path)
    definitions = data.get("channels")
    if not isinstance(definitions, list):
        raise ValueError("Channel configuration must contain a 'channels' list")

    channels = {}
    for definition in definitions:
        channel_id = definition.get("id")
        name = definition.get("name")
        required_tags = definition.get("required_tags", [])
        if not channel_id or not name or not isinstance(required_tags, list):
            raise ValueError("Invalid channel definition: %r" % definition)
        if channel_id in channels:
            raise ValueError("Duplicate channel ID: %s" % channel_id)
        channels[channel_id] = Channel(channel_id, name, tuple(required_tags))
    return channels


def episodes_for_channel(episodes, metadata, channel):
    """Return catalog episodes eligible for *channel*."""
    required_tags = set(channel.required_tags)
    if not required_tags:
        return tuple(episodes)

    eligible = []
    for episode in episodes:
        episode_tags = set(metadata.get(episode.episode_id, {}).get("tags", []))
        if required_tags.issubset(episode_tags):
            eligible.append(episode)
    return tuple(eligible)


def _load_json(path):
    path = Path(path)
    try:
        with path.open() as config_file:
            return json.load(config_file)
    except (OSError, ValueError) as error:
        raise ValueError("Could not load %s: %s" % (path, error))

