import unittest

from tools.analyze_commercials import (
    classify_clip,
    close_to_standard_duration,
    parse_silences,
    timed_units,
    manifest_paths,
)


class CommercialAnalysisTests(unittest.TestCase):
    def test_manifest_filter_accepts_multiple_years(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            manifests = Path(directory) / "manifests"
            manifests.mkdir()
            for name in ("1990-a.json", "1991-b.json", "1992-c.json"):
                (manifests / name).touch()
            paths = manifest_paths(directory, [1990, 1992])
            self.assertEqual([path.name for path in paths], ["1990-a.json", "1992-c.json"])

    def test_word_timestamps_are_preferred(self):
        units, mode = timed_units(
            {
                "segments": [
                    {
                        "words": [
                            {"start": 1, "end": 1.4, "word": "Brought"},
                            {"start": 1.4, "end": 1.6, "word": "to"},
                        ]
                    }
                ]
            }
        )
        self.assertEqual(mode, "word")
        self.assertEqual([unit["text"] for unit in units], ["Brought", "to"])

    def test_words_from_high_compression_hallucination_are_removed(self):
        units, mode = timed_units(
            {
                "segments": [
                    {
                        "compression_ratio": 13.0,
                        "words": [{"start": 1, "end": 2, "word": "FOX FOX FOX"}],
                    },
                    {
                        "compression_ratio": 1.2,
                        "words": [{"start": 3, "end": 4, "word": "McDonald's"}],
                    },
                ]
            }
        )
        self.assertEqual(mode, "word")
        self.assertEqual([unit["text"] for unit in units], ["McDonald's"])

    def test_sponsor_bumper_is_recommended_with_clean_boundaries(self):
        clip = {"start": 10, "end": 20, "duration": 10}
        units = [
            {"start": 10.4, "end": 11.0, "text": "The Simpsons"},
            {"start": 11.0, "end": 12.0, "text": "is brought to you by"},
            {"start": 12.0, "end": 14.0, "text": "Butterfinger"},
        ]
        result = classify_clip(clip, units, "word", ((9.9, 10.2), (19.8, 20.2)), 30)
        self.assertEqual(result["suggested_kind"], "sponsor-bumper")
        self.assertTrue(result["recommended_approved"])

    def test_speech_crossing_cut_is_fragment(self):
        clip = {"start": 10, "end": 20, "duration": 10}
        units = [{"start": 9.7, "end": 10.4, "text": "and"}]
        result = classify_clip(clip, units, "word", (), 30)
        self.assertEqual(result["suggested_kind"], "suspected-fragment")
        self.assertFalse(result["recommended_approved"])
        self.assertTrue(result["crosses_start"])

    def test_credits_language_is_rejected(self):
        clip = {"start": 0, "end": 30, "duration": 30}
        units = [
            {"start": 2, "end": 4, "text": "Executive producer"},
            {"start": 4, "end": 5, "text": "James Brooks"},
        ]
        result = classify_clip(clip, units, "word", ((29.8, 30.0),), 30)
        self.assertEqual(result["suggested_kind"], "credits")
        self.assertFalse(result["recommended_approved"])

    def test_program_promo_is_not_a_commercial(self):
        clip = {"start": 0, "end": 10, "duration": 10}
        units = [{"start": 1, "end": 8, "text": "On the next Seinfeld, Monday at 7:30"}]
        result = classify_clip(clip, units, "word", ((9.8, 10.0),), 10)
        self.assertEqual(result["suggested_kind"], "program-continuity")
        self.assertFalse(result["recommended_approved"])

    def test_manual_exclusion_wins_over_other_signals(self):
        clip = {"start": 0, "end": 30, "duration": 30}
        units = [{"start": 1, "end": 29, "text": "Call now to order"}]
        result = classify_clip(clip, units, "word", ((29.8, 30.0),), 30, True)
        self.assertEqual(result["suggested_kind"], "manually-excluded")
        self.assertFalse(result["recommended_approved"])

    def test_long_form_is_never_automatically_kept(self):
        clip = {"start": 0, "end": 45, "duration": 45}
        units = [{"start": 1, "end": 44, "text": "Buy this wonderful product today please"}]
        result = classify_clip(clip, units, "word", ((44.8, 45.0),), 45)
        self.assertEqual(result["suggested_kind"], "long-form-candidate")
        self.assertFalse(result["recommended_approved"])

    def test_long_sponsor_wording_is_still_rejected(self):
        clip = {"start": 0, "end": 40, "duration": 40}
        units = [
            {
                "start": 1,
                "end": 39,
                "text": "The Simpsons is brought to you by a sponsor",
            }
        ]
        result = classify_clip(clip, units, "word", ((39.8, 40.0),), 40)
        self.assertEqual(result["suggested_kind"], "long-form-candidate")
        self.assertFalse(result["recommended_approved"])

    def test_one_word_clip_is_too_uncertain_to_keep(self):
        clip = {"start": 0, "end": 30, "duration": 30}
        units = [{"start": 2, "end": 3, "text": "Yeah"}]
        result = classify_clip(clip, units, "word", ((29.8, 30.0),), 30)
        self.assertEqual(result["suggested_kind"], "uncertain")
        self.assertFalse(result["recommended_approved"])

    def test_silence_parser_and_standard_durations(self):
        output = "silence_start: 9.8\nsilence_end: 10.2 | silence_duration: 0.4"
        self.assertEqual(parse_silences(output), ((9.8, 10.2),))
        self.assertTrue(close_to_standard_duration(29.7))
        self.assertFalse(close_to_standard_duration(37.0))


if __name__ == "__main__":
    unittest.main()
