"""Episode selection with bounded recent-play avoidance."""

import random

from tv.channels import episodes_for_channel


class NoEligibleEpisodes(ValueError):
    """Raised when a channel has no matching local episodes."""


class EpisodeScheduler:
    """Select episodes for channels while avoiding recent repeats."""

    def __init__(
        self,
        episodes,
        metadata,
        recent_limit=12,
        random_source=None,
        recent_ids=None,
    ):
        if recent_limit < 0:
            raise ValueError("recent_limit cannot be negative")
        self._episodes = tuple(episodes)
        self._metadata = metadata
        self._recent_limit = recent_limit
        self._random = random_source or random.Random()
        self._recent_ids = list(recent_ids or ())[-recent_limit:] if recent_limit else []

    @property
    def recent_ids(self):
        return tuple(self._recent_ids)

    def choose_next(self, channel):
        """Choose and remember the next episode for *channel*."""
        eligible = episodes_for_channel(self._episodes, self._metadata, channel)
        if not eligible:
            raise NoEligibleEpisodes("No local episodes match channel %s" % channel.name)

        # Never exclude every item in a small channel. With nine Treehouse
        # episodes and a recent limit of twelve, this makes a complete circuit
        # before the oldest episode becomes eligible again.
        exclusion_count = min(self._recent_limit, max(0, len(eligible) - 1))
        excluded_ids = set(self._recent_ids[-exclusion_count:]) if exclusion_count else set()
        candidates = [
            episode for episode in eligible if episode.episode_id not in excluded_ids
        ]

        selected = self._random.choice(candidates)
        self._recent_ids.append(selected.episode_id)
        if self._recent_limit:
            self._recent_ids = self._recent_ids[-self._recent_limit :]
        else:
            self._recent_ids = []
        return selected

