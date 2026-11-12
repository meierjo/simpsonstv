# Local commercial library

Commercial video files are deliberately excluded from Git. Organize converted
clips by their original broadcast year:

```text
commercials/
  1989/
  1990/
  1991/
  ...
  1999/
```

Prefer one advertisement per file. Use a descriptive filename without relying
on it for rights or year metadata, for example:

```text
commercials/1993/1993 - Brand - Product - Short description.mp4
```

Encode for the existing player:

```bash
ffmpeg -i "input-file" -vf scale=-2:480 \
  -c:v libx264 -profile:v baseline -level 3.0 \
  -preset fast -crf 23 -pix_fmt yuv420p "output-file.mp4"
```

## Automatic reel importer

The importer downloads a saved source, detects black-screen transitions,
groups them into plausible 10-60 second advertisements, encodes Pi-compatible
candidate clips, and creates a manifest plus an HTML review page:

```bash
python3 tools/import_commercial_reel.py --year 1994
```

Use a local download instead of `yt-dlp` when preferred:

```bash
python3 tools/import_commercial_reel.py \
  --year 1994 --input "/path/to/commercial-break-reel.mp4"
```

Preview the proposed timestamps without encoding:

```bash
python3 tools/import_commercial_reel.py \
  --year 1994 --input "/path/to/reel.mp4" --dry-run
```

URL imports require `yt-dlp` and `ffmpeg` on the computer doing the
import. Detection is intentionally conservative. Watch the generated review
page before transferring clips to the TV.

Standard 13-35 second clips are now auto-classified as approved commercials.
Short clips are retained as possible sponsor bumpers, while clips longer than
35 seconds and unusual fragments remain unapproved for focused review. Tracked
overrides preserve confirmed examples such as the 1989 Simpsons sponsor bumper.

Download availability does not establish permission to redistribute a
commercial. Keep source, year, and rights notes for every clip. Do not include
commercial media in cloned cards or public releases unless its license or
permission allows that use.
