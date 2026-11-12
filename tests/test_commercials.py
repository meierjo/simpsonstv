import json
import random
import tempfile
import unittest
from pathlib import Path

from tv.catalog import Episode, EXPECTED_EPISODES
from tv.commercials import (
    CommercialClip,
    CommercialScheduler,
    broadcast_year_for_episode,
    load_approved_clips,
    load_broadcast_years,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class CommercialTests(unittest.TestCase):
    def test_broadcast_year_rules_cover_all_226_episodes(self):
        rules = load_broadcast_years(REPOSITORY_ROOT / "config" / "broadcast_years.json")
        years = []
        for season, episode_count in EXPECTED_EPISODES.items():
            for number in range(1, episode_count + 1):
                episode = Episode("S%02dE%02d" % (season, number), season, number, "", Path("x"))
                years.append(broadcast_year_for_episode(episode, {}, rules))
        self.assertEqual(len(years), 226)
        self.assertTrue(all(1989 <= year <= 1999 for year in years))

    def test_new_year_cutovers_match_original_broadcasts(self):
        rules = load_broadcast_years(REPOSITORY_ROOT / "config" / "broadcast_years.json")
        last_1993 = Episode("S05E10", 5, 10, "", Path("x"))
        first_1994 = Episode("S05E11", 5, 11, "", Path("x"))
        self.assertEqual(broadcast_year_for_episode(last_1993, {}, rules), 1993)
        self.assertEqual(broadcast_year_for_episode(first_1994, {}, rules), 1994)

    def test_explicit_air_date_overrides_season_rules(self):
        episode = Episode("S01E01", 1, 1, "", Path("x"))
        year = broadcast_year_for_episode(
            episode, {"S01E01": {"air_date": "2001-02-03"}}, {1: ((13, 1990),)}
        )
        self.assertEqual(year, 2001)

    def test_loader_uses_only_approved_existing_safe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifests").mkdir()
            (root / "1994").mkdir()
            (root / "1994" / "keep.mp4").touch()
            manifest = {
                "year": 1994,
                "clips": [
                    {"file": "1994/keep.mp4", "approved": True, "kind": "commercial"},
                    {"file": "1994/missing.mp4", "approved": True, "kind": "commercial"},
                    {"file": "1994/no.mp4", "approved": False, "kind": "commercial"},
                    {"file": "../outside.mp4", "approved": True, "kind": "commercial"},
                ],
            }
            (root / "manifests" / "1994.json").write_text(json.dumps(manifest))
            clips = load_approved_clips(root)
            self.assertEqual(clips, (CommercialClip((root / "1994" / "keep.mp4").resolve(), 1994),))

    def test_scheduler_chooses_bumper_then_matching_year_commercial(self):
        clips = (
            CommercialClip(Path("bumper.mp4"), 1989, "sponsor-bumper"),
            CommercialClip(Path("ad-a.mp4"), 1989, "commercial"),
            CommercialClip(Path("ad-b.mp4"), 1989, "commercial"),
            CommercialClip(Path("wrong-year.mp4"), 1990, "commercial"),
        )
        scheduler = CommercialScheduler(clips, random_source=random.Random(1))
        first = scheduler.choose_preroll(1989)
        second = scheduler.choose_preroll(1989)
        self.assertEqual(first[0].kind, "sponsor-bumper")
        self.assertTrue(all(clip.year == 1989 for clip in first))
        self.assertNotEqual(first[1].path, second[1].path)

    def test_missing_year_has_no_preroll(self):
        scheduler = CommercialScheduler((CommercialClip(Path("ad.mp4"), 1994),))
        self.assertEqual(scheduler.choose_preroll(1993), ())


if __name__ == "__main__":
    unittest.main()
