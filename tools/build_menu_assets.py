#!/usr/bin/env python3
"""Build the static 640x480 channel-menu artwork and H.264 clips."""

from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = REPOSITORY_ROOT / "assets"
WIDTH = 640
HEIGHT = 480
LEFT_CARD = (28, 112, 306, 335)
RIGHT_CARD = (334, 112, 612, 335)
SPECIAL_LEFT_CARD = (18, 112, 208, 335)
SPECIAL_CENTER_CARD = (225, 112, 415, 335)
SPECIAL_RIGHT_CARD = (432, 112, 622, 335)
SHUTDOWN_CARD = (70, 345, 570, 445)


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


def draw_card(
    draw,
    rectangle,
    eyebrow,
    title_lines,
    subtitle,
    color,
    active,
    title_size=37,
):
    border = (255, 226, 85) if active else (242, 234, 245)
    border_width = 10 if active else 5
    draw.rectangle(rectangle, fill=(15, 9, 30), outline=border, width=border_width)
    inset = tuple(value + offset for value, offset in zip(rectangle, (9, 9, -9, -9)))
    draw.rectangle(inset, fill=color)
    center_x = (rectangle[0] + rectangle[2]) // 2
    centered(draw, eyebrow, center_x, rectangle[1] + 24, font(24), (28, 15, 43))
    for index, line in enumerate(title_lines):
        centered(
            draw,
            line,
            center_x,
            rectangle[1] + 80 + index * 43,
            font(title_size),
            (255, 249, 218),
        )
    centered(draw, subtitle, center_x, rectangle[1] + 190, font(18), (28, 15, 43))
    if active:
        centered(draw, "ON AIR", center_x, rectangle[1] + 222, font(21), (255, 226, 85))


def build_image(active_channel, page=0):
    image = Image.new("RGB", (WIDTH, HEIGHT), (39, 20, 73))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 17), fill=(247, 196, 54))
    draw.rectangle((0, 18, WIDTH, 27), fill=(40, 191, 190))
    draw.rectangle((0, 28, WIDTH, 34), fill=(236, 83, 146))
    centered(draw, "TOUCH TUNER", WIDTH // 2, 48, font(45), (255, 246, 197))
    page_label = "MAIN CHANNELS  |  SWIPE LEFT FOR SPECIALS" if page == 0 else "SPECIALS  |  SWIPE RIGHT FOR MAIN"
    centered(draw, page_label, WIDTH // 2, 88, font(17), (216, 205, 231))
    if page == 0:
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
    else:
        draw_card(
            draw,
            SPECIAL_LEFT_CARD,
            "HOLIDAY",
            ("FESTIVE", "FAVORITES"),
            "SEASONAL TV",
            (38, 151, 99),
            active_channel == "holiday-special",
            title_size=27,
        )
        draw_card(
            draw,
            SPECIAL_CENTER_CARD,
            "WANTED",
            ("SIDESHOW", "BOB"),
            "CRIMINAL TV",
            (176, 54, 57),
            active_channel == "sideshow-bob",
            title_size=29,
        )
        draw_card(
            draw,
            SPECIAL_RIGHT_CARD,
            "HEY HEY!",
            ("KRUSTY", "CLASSICS"),
            "CLOWN TV",
            (224, 132, 37),
            active_channel == "krusty-classics",
            title_size=28,
        )
    draw.rectangle(SHUTDOWN_CARD, fill=(101, 35, 63), outline=(242, 234, 245), width=4)
    centered(draw, "GOOD NIGHT, SPRINGFIELD", WIDTH // 2, 357, font(25), (255, 246, 197))
    centered(draw, "HOLD 1 SECOND TO SHUT DOWN", WIDTH // 2, 402, font(17), (255, 226, 85))
    return image


def build_now_playing_background():
    banner_height = 180
    image = Image.new("RGB", (WIDTH, banner_height), (22, 11, 40))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 8), fill=(247, 196, 54))
    draw.rectangle((0, 8, WIDTH, 14), fill=(40, 191, 190))
    centered(draw, "NOW PLAYING", WIDTH // 2, 19, font(25), (255, 246, 197))
    draw.line((40, 53, 600, 53), fill=(236, 83, 146), width=4)
    return image


def build_goodnight_image():
    image = Image.new("RGB", (WIDTH, HEIGHT), (18, 9, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 20), fill=(247, 196, 54))
    centered(draw, "GOOD NIGHT,", WIDTH // 2, 140, font(58), (255, 246, 197))
    centered(draw, "SPRINGFIELD", WIDTH // 2, 215, font(58), (255, 226, 85))
    centered(draw, "SHUTTING DOWN SAFELY...", WIDTH // 2, 330, font(26), (40, 191, 190))
    centered(draw, "UNPLUG AFTER THE SCREEN GOES DARK", WIDTH // 2, 382, font(18), (223, 214, 235))
    return image


def encode_clip(png_path, mp4_path, duration=12):
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "25",
            "-i",
            str(png_path),
            "-t",
            str(duration),
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
    channel_ids = (
        "springfield-tv",
        "treehouse-after-dark",
        "holiday-special",
        "sideshow-bob",
        "krusty-classics",
    )
    for page in (0, 1):
        for channel_id in channel_ids:
            stem = "channel_menu_page%d_%s" % (
                page,
                channel_id.replace("-", "_"),
            )
            png_path = ASSET_DIRECTORY / (stem + ".png")
            mp4_path = ASSET_DIRECTORY / (stem + ".mp4")
            build_image(channel_id, page=page).save(png_path)
            encode_clip(png_path, mp4_path)
            print("Built %s" % mp4_path)

    png_path = ASSET_DIRECTORY / "now_playing_background.png"
    mp4_path = ASSET_DIRECTORY / "now_playing_background.mp4"
    build_now_playing_background().save(png_path)
    encode_clip(png_path, mp4_path, duration=4)
    print("Built %s" % mp4_path)

    png_path = ASSET_DIRECTORY / "good_night_springfield.png"
    mp4_path = ASSET_DIRECTORY / "good_night_springfield.mp4"
    build_goodnight_image().save(png_path)
    encode_clip(png_path, mp4_path)
    print("Built %s" % mp4_path)


if __name__ == "__main__":
    main()

