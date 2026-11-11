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

Download availability does not establish permission to redistribute a
commercial. Keep source, year, and rights notes for every clip. Do not include
commercial media in cloned cards or public releases unless its license or
permission allows that use.
