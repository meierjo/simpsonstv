import tempfile
import unittest
from pathlib import Path

from tv.catalog import Episode
from tv.channels import Channel
from tv.now_playing import NowPlayingStore


class NowPlayingTests(unittest.TestCase):
    def test_current_program_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = NowPlayingStore(Path(directory) / "now_playing.json")
            episode = Episode(
                "S05E10", 5, 10, "Springfield", Path("S05E10.mp4")
            )
            channel = Channel("springfield-tv", "Channel 6", ())

            saved = store.save(episode, channel, air_year=1993)

            self.assertEqual(store.load(), saved)
            self.assertEqual(saved["title"], "Springfield")
            self.assertEqual(saved["air_year"], 1993)

    def test_missing_or_corrupt_metadata_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "now_playing.json"
            store = NowPlayingStore(path)
            self.assertIsNone(store.load())
            path.write_text("not json")
            self.assertIsNone(store.load())


if __name__ == "__main__":
    unittest.main()
