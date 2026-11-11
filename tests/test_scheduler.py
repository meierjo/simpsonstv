import random
import unittest
from pathlib import Path

from tv.catalog import Episode
from tv.channels import Channel, episodes_for_channel, load_channels, load_episode_metadata
from tv.scheduler import EpisodeScheduler, NoEligibleEpisodes


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def make_episode(episode_id):
    season = int(episode_id[1:3])
    episode_number = int(episode_id[4:6])
    return Episode(
        episode_id=episode_id,
        season=season,
        episode=episode_number,
        title="Episode " + episode_id,
        path=Path(episode_id + ".mp4"),
    )


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.metadata = load_episode_metadata(REPOSITORY_ROOT / "config" / "episodes.json")
        self.channels = load_channels(REPOSITORY_ROOT / "config" / "channels.json")
        self.episodes = tuple(make_episode(episode_id) for episode_id in self.metadata)

    def test_treehouse_channel_contains_all_nine_tagged_episodes(self):
        eligible = episodes_for_channel(
            self.episodes,
            self.metadata,
            self.channels["treehouse-after-dark"],
        )

        self.assertEqual(len(eligible), 9)
        self.assertEqual(
            {episode.episode_id for episode in eligible}, set(self.metadata)
        )

    def test_normal_channel_includes_every_episode(self):
        eligible = episodes_for_channel(
            self.episodes,
            self.metadata,
            self.channels["springfield-tv"],
        )

        self.assertEqual(eligible, self.episodes)

    def test_scheduler_plays_each_treehouse_before_a_repeat(self):
        scheduler = EpisodeScheduler(
            self.episodes,
            self.metadata,
            recent_limit=12,
            random_source=random.Random(1990),
        )
        channel = self.channels["treehouse-after-dark"]

        first_cycle = [scheduler.choose_next(channel).episode_id for _ in range(9)]
        tenth = scheduler.choose_next(channel).episode_id

        self.assertEqual(len(set(first_cycle)), 9)
        self.assertNotEqual(tenth, first_cycle[-1])

    def test_recent_limit_avoids_immediate_repeats(self):
        episodes = (make_episode("S01E01"), make_episode("S01E02"))
        channel = Channel("test", "Test", ())
        scheduler = EpisodeScheduler(
            episodes,
            {},
            recent_limit=1,
            random_source=random.Random(1),
        )

        selections = [scheduler.choose_next(channel).episode_id for _ in range(6)]

        self.assertEqual(selections, ["S01E01", "S01E02"] * 3)

    def test_empty_channel_raises_clear_error(self):
        scheduler = EpisodeScheduler(self.episodes, self.metadata)
        channel = Channel("empty", "Empty", ("not-a-real-tag",))

        with self.assertRaises(NoEligibleEpisodes):
            scheduler.choose_next(channel)


if __name__ == "__main__":
    unittest.main()

