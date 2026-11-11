# Custom Simpsons TV

This repository is our maintained version of Brandon Withrow's desktop Simpsons
TV project. It keeps the original Raspberry Pi Zero and Waveshare display build
as a small, understandable baseline while adding reliable media handling,
selectable playback modes, Easter eggs, and custom packaging.

## Original project

The hardware design and original playback scripts were created by Brandon
Withrow (`buba447`):

- Build guide: <https://withrow.io/simpsons-tv-build-guide-waveshare>
- Upstream source: <https://github.com/buba447/simpsonstv>

The original repository is retained locally as the Git remote named `upstream`.

## Current hardware behavior

- The Pi and video player remain running continuously.
- The front latching switch controls the screen backlight and audio output.
- The volume control is an analog potentiometer.
- Episodes are H.264 MP4 files, 480 pixels high, played by OMXPlayer.

## Local media

Episodes are deliberately excluded from Git. `videos/link_to_vids` may point to
a local encoded-video directory for catalog inspection and testing, but neither
the link nor the media it references should be committed.

## Encoding

Use Python 3 to run the encoder from the `videos` directory:

```bash
python3 encode.py
```

Encoded files are written to `videos/encoded`. The encoder invokes FFmpeg
without a shell, so filenames containing spaces, parentheses, apostrophes, or
characters such as `$` are handled literally.

Run the encoder regression tests from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

## Planned extensions

- Episode catalog validation and metadata
- Normal, Halloween, holiday, and character-focused playback modes
- Recently-played avoidance
- Period-correct commercials selected by original broadcast year
- Secret touchscreen sequence or hidden hardware control
- Custom retail-box artwork and print-ready packaging

This project does not include television episodes or other copyrighted media.
