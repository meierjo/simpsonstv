#!/usr/bin/env python3
"""Build the static 640x480 channel-menu artwork and H.264 clips."""

from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = REPOSITORY_ROOT / "assets"
WIDTH = 640
HEIGHT = 480
LEFT_CARD = (28, 112, 306, 372)
RIGHT_CARD = (334, 112, 612, 372)


def font(size):
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def centered(draw, text, center_x, y, text_font, fill):
    box = draw.textbbox((0, 0), text, font=text_font)
    width = box[2] - box[0]
    draw.text((center_x - width / 2, y), text, font=text_font, fill=fill)


def draw_card(draw, rectangle, eyebrow, title_lines, subtitle, color, active):
    border = (255, 226, 85) if active else (242, 234, 245)
    border_width = 10 if active else 5
    draw.rectangle(rectangle, fill=(15, 9, 30), outline=border, width=border_width)
    inset = tuple(value + offset for value, offset in zip(rectangle, (9, 9, -9, -9)))
    draw.rectangle(inset, fill=color)
    center_x = (rectangle[0] + rectangle[2]) // 2
    centered(draw, eyebrow, center_x, rectangle[1] + 24, font(24), (28, 15, 43))
    for index, line in enumerate(title_lines):
        centered(draw, line, center_x, rectangle[1] + 80 + index * 48, font(37), (255, 249, 218))
    centered(draw, subtitle, center_x, rectangle[1] + 190, font(21), (28, 15, 43))
    if active:
        centered(draw, "ON AIR", center_x, rectangle[1] + 222, font(21), (255, 226, 85))


def build_image(active_channel):
    image = Image.new("RGB", (WIDTH, HEIGHT), (39, 20, 73))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 17), fill=(247, 196, 54))
    draw.rectangle((0, 18, WIDTH, 27), fill=(40, 191, 190))
    draw.rectangle((0, 28, WIDTH, 34), fill=(236, 83, 146))
    centered(draw, "TOUCH TUNER", WIDTH // 2, 48, font(45), (255, 246, 197))
    centered(draw, "CHOOSE YOUR CHANNEL", WIDTH // 2, 88, font(20), (216, 205, 231))
    draw_card(
        draw,
        LEFT_CARD,
        "CHANNEL 6",
        ("SPRINGFIELD", "TV"),
        "RANDOM EPISODES",
        (42, 176, 195),
        active_channel == "springfield-tv",
    )
    draw_card(
        draw,
        RIGHT_CARD,
        "AFTER DARK",
        ("TREEHOUSE",),
        "HALLOWEEN",
        (210, 73, 139),
        active_channel == "treehouse-after-dark",
    )
    centered(draw, "TAP A CHANNEL  -  WAIT TO CANCEL", WIDTH // 2, 425, font(20), (223, 214, 235))
    centered(draw, "NOW WITH SECRET MODES!", WIDTH // 2, 452, font(16), (255, 226, 85))
    return image


def encode_clip(png_path, mp4_path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "25",
            "-i",
            str(png_path),
            "-t",
            "12",
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-preset",
            "slow",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(mp4_path),
        ],
        check=True,
    )


def main():
    ASSET_DIRECTORY.mkdir(exist_ok=True)
    for channel_id in ("springfield-tv", "treehouse-after-dark"):
        stem = "channel_menu_" + channel_id.replace("-", "_")
        png_path = ASSET_DIRECTORY / (stem + ".png")
        mp4_path = ASSET_DIRECTORY / (stem + ".mp4")
        build_image(channel_id).save(png_path)
        encode_clip(png_path, mp4_path)
        print("Built %s" % mp4_path)


if __name__ == "__main__":
    main()

