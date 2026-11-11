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

## Library audit

The catalog tool checks a video directory without renaming or modifying any
files. It accepts both zero-padded names such as `S03E01` and existing names
such as `S03E1`, normalizing both to the same episode ID in memory:

```bash
python3 tools/catalog.py /path/to/encoded/videos
```

Add `--strict` when using it in an automated check. Strict mode exits with a
failure status when an episode is missing, duplicated, outside seasons 1-10,
or has a filename without a recognizable season and episode number.

Preview the scheduler without playing any video:

```bash
python3 tools/preview_channel.py /path/to/encoded/videos \
  --channel treehouse-after-dark --count 9
```

Channel definitions live in `config/channels.json`; episode tags live in
`config/episodes.json`.

### Switching channels before the touch UI

The player reads a small persistent state file before choosing each episode.
List or select channels from the Pi command line:

```bash
python3 tools/set_channel.py --list
python3 tools/set_channel.py treehouse-after-dark
python3 tools/set_channel.py springfield-tv
```

The selected channel takes effect after the current episode. Restart
`tvplayer.service` after selecting a channel to switch immediately. Recent
episode history is preserved across service restarts.

The updated player requires Python 3. Copy `systemd/tvplayer.service` to
`/etc/systemd/system/tvplayer.service` on the original build, then reload
systemd before restarting it.

### Touch prototype

The first touch milestone uses a three-finger hold for two seconds to toggle
between Springfield TV and Treehouse After Dark. The player notices the state
change, ends the current video, and selects from the new channel immediately.
This direct toggle is a prototype; the same gesture will open the visual
channel overlay in the finished experience.

The listener uses the Linux `evdev` interface and the existing Goodix
capacitive touchscreen. Install `python3-evdev`, then install and enable
`systemd/tvtouch.service`. The service runs as `pi` with supplementary access
to the `input` group; no new hardware or permanent user-group change is needed.

### Canonical filenames

The project uses `SxxExx - Title.mp4` for episode files. Preview a safe rename
of an existing library on the Pi:

```bash
cd ~/simpsonstv
python3 tools/rename_episodes.py ~/simpsonstv/videos
```

Review every proposed change, then apply the same validated plan:

```bash
python3 tools/rename_episodes.py ~/simpsonstv/videos --apply
```

The renamer refuses to run when duplicate IDs, out-of-range episodes, unknown
video filenames, or destination collisions are present. It never changes
video contents.

Future encoding runs produce canonical names automatically. A title in
`config/episodes.json` takes precedence; otherwise the title already present
in the source filename is normalized. Tags for secret channels stay in the
metadata rather than being embedded in filenames.

## Planned extensions

- Episode catalog validation and metadata
- Normal, Halloween, holiday, and character-focused playback modes
- Recently-played avoidance
- Period-correct commercials selected by original broadcast year
- Secret touchscreen channel controls
- Custom retail-box artwork and print-ready packaging

This project does not include television episodes or other copyrighted media.
