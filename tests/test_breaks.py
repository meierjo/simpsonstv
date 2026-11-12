import json
import tempfile
import unittest
from pathlib import Path

from tools.set_break_cue import parse_time, set_episode_cue
from tv.breaks import break_cue_for_episode, format_omx_position, load_break_cues
from tv.catalog import Episode


class BreakCueTests(unittest.TestCase):
    def make_episode(self, episode_id="S05E10"):
        return Episode(episode_id, 5, 10, "Test", Path("test.mp4"))

    def test_episode_cue_beats_season_default(self):
        cues = {"episode_cues": {"S05E10": 82.0}, "season_defaults": {5: 70.0}}
        self.assertEqual(break_cue_for_episode(self.make_episode(), cues), 82.0)

    def test_uncued_episode_has_no_break(self):
        self.assertIsNone(break_cue_for_episode(self.make_episode(), {}))

    def test_omx_position_format(self):
        self.assertEqual(format_omx_position(75), "00:01:15")

    def test_human_time_parser(self):
        self.assertEqual(parse_time("1:15"), 75.0)
        self.assertEqual(parse_time("00:01:15.5"), 75.5)

    def test_set_and_remove_episode_cue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cues.json"
            path.write_text('{"episode_cues": {}, "season_defaults": {}}')
            set_episode_cue(path, "S05E10", 75.0)
            self.assertEqual(load_break_cues(path)["episode_cues"]["S05E10"], 75.0)
            set_episode_cue(path, "S05E10", None)
            self.assertNotIn("S05E10", json.loads(path.read_text())["episode_cues"])


if __name__ == "__main__":
    unittest.main()
