"""Encode local video files for the Raspberry Pi Simpsons TV.

FFmpeg is invoked with an argument list rather than a shell command. This keeps
filenames literal, including names containing spaces, parentheses, apostrophes,
and dollar signs.
"""

from pathlib import Path
import subprocess


VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".avi"}


def is_video(path):
    """Return True when *path* has a supported video extension."""
    return path.suffix.lower() in VIDEO_SUFFIXES


def build_encode_command(input_path, output_path):
    """Build the exact FFmpeg argument list used for one conversion."""
    return [
        "ffmpeg",
        "-i",
        str(input_path),
        "-vf",
        "scale=-2:480",
        "-c:v",
        "libx264",
        "-profile:v",
        "baseline",
        "-level",
        "3.0",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]


def find_videos(directory, destination_directory):
    """Find source videos while excluding the encoder's destination tree."""
    for path in directory.rglob("*"):
        if not path.is_file() or not is_video(path):
            continue
        try:
            path.relative_to(destination_directory)
        except ValueError:
            yield path


def encode_directory(directory):
    """Encode every supported video below *directory* into `encoded`."""
    directory = Path(directory).resolve()
    destination_directory = directory / "encoded"
    destination_directory.mkdir(exist_ok=True)

    source_videos = list(find_videos(directory, destination_directory))
    for input_path in source_videos:
        output_path = destination_directory / (input_path.stem + ".mp4")
        if output_path.is_file():
            continue

        print("Encoding %s" % input_path.name)
        subprocess.run(
            build_encode_command(input_path, output_path),
            check=True,
        )


def main():
    encode_directory(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
