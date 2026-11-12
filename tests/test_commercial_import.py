import json
import tempfile
import unittest
from pathlib import Path

from tools.import_commercial_reel import (
    choose_segments,
    load_saved_source,
    parse_black_intervals,
    parse_duration,
    parse_scene_points,
    safe_stem,
    write_manifest,
)


class CommercialImportTests(unittest.TestCase):
    def test_ffmpeg_duration_is_parsed_without_ffprobe(self):
        output = "Duration: 01:02:03.50, start: 0.000000, bitrate: 500 kb/s"
        self.assertEqual(parse_duration(output), 3723.5)

    def test_blackdetect_output_is_parsed(self):
        output = """
[blackdetect] black_start:14.8 black_end:15.2 black_duration:0.4
[blackdetect] black_start:44.9 black_end:45.1 black_duration:0.2
"""
        self.assertEqual(
            parse_black_intervals(output), ((14.8, 15.2), (44.9, 45.1))
        )

    def test_scene_cut_timestamps_are_parsed(self):
        output = "n:1 pts:100 pts_time:3.25 pos:0\nn:2 pts_time:33.50 pos:1"
        self.assertEqual(parse_scene_points(output), (3.25, 33.5))

    def test_segment_planner_prefers_normal_ad_lengths(self):
        black = ((14.8, 15.2), (29.8, 30.2), (59.8, 60.2))
        self.assertEqual(
            choose_segments(90.0, black),
            ((0.0, 15.0), (15.0, 30.0), (30.0, 60.0), (60.0, 90.0)),
        )

    def test_internal_black_frame_is_not_forced_into_a_tiny_clip(self):
        black = ((4.8, 5.2), (14.8, 15.2), (29.8, 30.2))
        segments = choose_segments(45.0, black)
        self.assertNotIn((0.0, 5.0), segments)
        self.assertEqual(segments[-1], (30.0, 45.0))

    def test_short_leading_slate_is_discarded(self):
        black = ((3.8, 4.2), (13.8, 14.2), (43.8, 44.2))
        self.assertEqual(
            choose_segments(44.0, black), ((4.0, 14.0), (14.0, 44.0))
        )

    def test_two_supported_thirty_second_ads_beat_one_sixty(self):
        black = ((29.3, 29.7),)
        self.assertEqual(
            choose_segments(59.0, black), ((0.0, 29.5), (29.5, 59.0))
        )

    def test_saved_source_selection_is_one_based(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {"year": 1994, "url": "first"},
                            {"year": 1994, "url": "second"},
                        ]
                    }
                )
            )
            self.assertEqual(load_saved_source(path, 1994, 2)["url"], "second")

    def test_manifest_starts_unapproved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            write_manifest(
                path,
                Path(directory),
                1994,
                Path("reel.mp4"),
                "https://example.test/reel",
                ((0.0, 15.0),),
                (Path(directory) / "1994" / "clip.mp4",),
            )
            payload = json.loads(path.read_text())
            self.assertEqual(payload["status"], "needs-review")
            self.assertFalse(payload["clips"][0]["approved"])
            self.assertEqual(payload["clips"][0]["file"], "1994/clip.mp4")

    def test_safe_stem_is_shell_and_filename_friendly(self):
        self.assertEqual(safe_stem(Path("A Reel: 1994!?.mp4")), "a-reel-1994")


if __name__ == "__main__":
    unittest.main()
