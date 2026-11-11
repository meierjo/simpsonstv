import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from videos import encode


class EncodeTests(unittest.TestCase):
    def test_command_preserves_shell_sensitive_filename(self):
        source = Path(
            "/media/The Simpsons S05E10 $pringfield "
            "(Or, How I Learned to Stop Worrying and Love Legalized Gambling).mp4"
        )
        destination = Path("/media/encoded") / source.name

        command = encode.build_encode_command(source, destination)

        self.assertEqual(command[0], "ffmpeg")
        self.assertEqual(command[2], str(source))
        self.assertEqual(command[-1], str(destination))
        self.assertIn("$pringfield", command[2])

    @mock.patch.object(subprocess, "run")
    def test_encode_directory_passes_filename_without_a_shell(self, run):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "Episode $pecial (Test).mp4"
            source.touch()

            encode.encode_directory(directory)

            run.assert_called_once()
            command = run.call_args.args[0]
            self.assertEqual(command[2], str(source.resolve()))
            self.assertEqual(
                command[-1],
                str(
                    directory.resolve()
                    / "encoded"
                    / "Episode $pecial (Test).mp4"
                ),
            )
            self.assertTrue(run.call_args.kwargs["check"])
            self.assertNotIn("shell", run.call_args.kwargs)

    @mock.patch.object(subprocess, "run")
    def test_existing_output_is_not_overwritten(self, run):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "episode.mkv"
            source.touch()
            destination = directory / "encoded"
            destination.mkdir()
            (destination / "episode.mp4").touch()

            encode.encode_directory(directory)

            run.assert_not_called()

    @mock.patch.object(subprocess, "run")
    def test_episode_output_uses_canonical_name(self, run):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "The Simpsons S03E7 old title.mkv"
            source.touch()

            encode.encode_directory(
                directory,
                {"S03E07": {"title": "Treehouse of Horror II"}},
            )

            command = run.call_args.args[0]
            self.assertEqual(
                command[-1],
                str(directory.resolve() / "encoded" / "S03E07 - Treehouse of Horror II.mp4"),
            )


if __name__ == "__main__":
    unittest.main()
