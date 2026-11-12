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

Hold one finger on the screen for two seconds to open the full-screen channel
menu. Playback pauses while the menu is visible. Release the opening touch,
then tap a large channel card; playback resumes immediately in that mode. The
menu closes without changing channels after ten seconds of inactivity.

The listener uses the Linux `evdev` interface and the existing Goodix
capacitive touchscreen. The menu itself is a tiny pre-rendered H.264 clip
shown through OMXPlayer, avoiding the console and graphics overhead of a
second UI framework. Install `python3-evdev`, then install and enable
`systemd/tvtouch.service`. The service runs as `pi` with supplementary access
to the `input` and `video` groups. If the menu cannot initialize, the gesture
safely falls back to the original direct channel toggle.

### Safe shutdown

The third Touch Tuner card requires a continuous three-second hold. It plays a
short confirmation clip and creates a local shutdown request. A root-owned
systemd path unit handles the privileged operating-system shutdown, so the
touch listener itself continues to run as the unprivileged `pi` user.

Install the shutdown units once on the Pi:

```bash
sudo cp systemd/tvpower.service systemd/tvpower.path /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tvpower.path
```

The request file is removed before shutdown so it cannot cause a shutdown loop
on the next boot.

## Curated channels

In addition to Springfield TV and Treehouse After Dark, the metadata now
defines Holiday Special, Sideshow Bob Marathon, and Krusty Classics. These can
be previewed or selected from the command line while the touch menu gains
pagination in a later interface pass:

```bash
python3 tools/preview_channel.py ~/simpsonstv/videos --channel holiday-special
python3 tools/set_channel.py sideshow-bob
python3 tools/set_channel.py krusty-classics
```

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

## Commercial television

Reviewed local commercials can play immediately before each episode using the
episode's actual original broadcast year. See `commercials/README.md` for the
review, approval, transfer, and disable commands. Sponsor bumpers are treated
as a separate first-class preroll and play before the year's commercial.

Commercial playback is fail-open: no media, no matching year, or an unplayable
ad never prevents the selected episode from starting.

### Commercials after the opening

An episode with a verified cue in `config/break_cues.json` uses the more
television-like sequence:

```text
episode opening → sponsor bumper/commercial → resume episode
```

Episodes without a cue retain the safe commercial-before-episode sequence. We
do not apply one guessed timestamp to the entire library because opening and
cold-open lengths vary. Add a cue after noting the desired timestamp:

```bash
python3 tools/set_break_cue.py S05E10 1:15
```

The cue accepts seconds, `mm:ss`, or `hh:mm:ss`. Remove a bad cue with:

```bash
python3 tools/set_break_cue.py S05E10 --remove
```

OMXPlayer stops the opening segment under controller supervision and resumes
the same file with its documented `--pos` option. A channel change still stops
the complete player process group at any point in the sequence.

#### Detecting and reviewing intro cues

Run detection on the Mac, not the Pi. It requires FFmpeg and Chromaprint's
`fpcalc`; Homebrew installs the latter with `brew install chromaprint`.

Analyze one season at a time. The tool reads embedded chapter markers, compares
Chromaprint audio across peer episodes, caches fingerprints, and makes paired
five-second previews without modifying the episode files:

```bash
python3 tools/analyze_intros.py /path/to/encoded --season 5
```

Review every proposed cut in the private localhost UI:

```bash
python3 tools/review_intro_cues.py \
  analysis/intros/season-05-candidates.json
```

Compare **Before cut** with **After resume**, adjust the timestamp if needed,
check **Approved**, and save. Generated fingerprints and previews stay under
the ignored `analysis/intros/` directory.

Export only approved cues into the player configuration:

```bash
python3 tools/review_intro_cues.py \
  analysis/intros/season-05-candidates.json \
  --export config/break_cues.json
```

### Black transitions between videos

OMXPlayer briefly reveals the Linux console when one video closes and the next
opens. The optional `tvconsole.service` keeps tty1 black so these transitions
look intentional. Install it on the Pi after confirming SSH access:

```bash
sudo cp systemd/tvconsole.service /etc/systemd/system/
sudo cp systemd/tvplayer.service /etc/systemd/system/
sudo systemctl disable --now getty@tty1.service
sudo systemctl daemon-reload
sudo systemctl enable --now tvconsole.service
sudo systemctl restart tvplayer.service
```

This disables only the visible login prompt on tty1; SSH is unaffected. With a
keyboard attached, `Ctrl+Alt+F2` opens another local virtual terminal. Restore
the original tty1 prompt with:

```bash
sudo systemctl disable --now tvconsole.service
sudo systemctl enable --now getty@tty1.service
```

## Planned extensions

- Episode catalog validation and metadata
- Normal, Halloween, holiday, and character-focused playback modes
- Recently-played avoidance
- Secret touchscreen channel controls
- Custom retail-box artwork and print-ready packaging

This project does not include television episodes or other copyrighted media.
