# Simpsons TV Experience Plan

## The idea

This should feel like a tiny television from an alternate 1990s: turn the front
knob on and whatever is broadcasting is what you get. It should be charming,
fast, and understandable without a menu. The special features should reveal
themselves through play, not make the TV feel like a streaming app.

The project starts with the original Brandon Withrow hardware and code, keeps
the always-playing illusion, and adds dependable playback, curated modes,
period commercials, tiny broadcast graphics, and a safe way to shut down.

## Experience principles

1. **It is a television, not a media browser.** No episode picker is required
   for normal use.
2. **The front knob stays obvious.** It controls the visible and audible TV,
   just as it does in the original build.
3. **Surprises are optional.** Normal random playback remains the default.
4. **No immediate repeats.** The TV remembers enough recent episodes to keep
   randomness from feeling broken.
5. **Graphics are brief.** A mode card or station ident should add flavor
   without delaying the show.
6. **The Pi must remain recoverable.** A broken video or malformed filename
   cannot stop the channel permanently.

## What we have

- Raspberry Pi Zero and Waveshare 2.8-inch 640x480 display
- GPIO 26 latching front power switch
- GPIO 18 display backlight control
- GPIO 19 PWM audio output
- Analog volume potentiometer and mono speaker
- Original Python scripts using OMXPlayer
- 225 encoded episodes from seasons 1-10; S05E10 is being restored, bringing
  the expected total to 226
- Original enclosure models and build guide

The front switch does not shut down the Pi. It turns the backlight and audio
path on or off while playback continues, which is central to the original
"always broadcasting" effect.

## Controls

### Front power knob

- **On:** enable the display backlight and audio output.
- **Off:** blank and mute the TV while the episode continues.
- The normal behavior should not change when modes are added.

Because this is a latching switch, it is not a good long-press control. Rapid
toggle sequences are technically possible, but they make the screen flash and
would be hard to discover or remember.

### Recommended secret button

Add one small momentary button on the underside or concealed behind the VCR.
GPIO 27 is the leading candidate because it is not assigned by the current
guide, but it must be verified on the assembled Waveshare hardware before any
soldering.

- **Short press:** cycle to the next special channel.
- **Double press:** return to normal random television.
- **Hold 2 seconds:** show the current channel card again.
- **Hold 5 seconds:** begin a safe operating-system shutdown, with a visible
  "GOOD NIGHT, SPRINGFIELD" confirmation before it is safe to unplug.

The exact physical placement should be tested with the printed shell before a
hole is added to the model. A removable VCR or an underside pinhole button
would preserve the original appearance.

## Channels and Easter eggs

The working term for a playback mode is **channel**. Channels select from a
tagged episode catalog; they do not contain hard-coded filename lists.

### Launch channels

1. **Channel 6 - Springfield TV**: all episodes, shuffled, with recent-play
   avoidance.
2. **Treehouse After Dark**: every `Treehouse of Horror` episode in seasons
   2-10, shuffled or played chronologically.
3. **Holiday Special**: Halloween, Thanksgiving, and Christmas-tagged
   episodes, selected by the current season when possible.

### Later channels

- **Krusty Classics**: Krusty-focused stories and short station bumpers.
- **Sideshow Bob Marathon**
- **Homer's Greatest Ideas**
- **Bart After Dark**
- **Ladies of Springfield**: Lisa- and Marge-focused stories.
- **Two-Parter Night**: linked episodes remain together and in order.
- **Original Broadcast**: chronological playback from season 1 onward.
- **Lucky Seven**: a deliberately rare surprise channel selected after a
  particular button sequence or date.

Tags live in metadata and can overlap. For example, an episode can be tagged
`halloween`, `bart`, and `sideshow-bob` without duplicating the media file.

## Broadcast flow

Normal episode transition:

1. Select an eligible episode that is not in recent history.
2. Look up its original air date and broadcast year.
3. Optionally select a cleared commercial block from the same year.
4. Play a very short station ident or channel card.
5. Play the commercial block.
6. Play the episode.
7. Record completion and choose the next broadcast.

If metadata or a commercial is missing, the episode still plays. Flavor must
never become a single point of failure.

### Commercial policy

- Commercials are a separate, optional local library and are never committed
  to Git.
- Each item records year, duration, source, and rights/availability notes.
- Exact-year matching is preferred; a configurable adjacent-year fallback can
  be used when a year has too little material.
- Keep the default block short: roughly one to three spots.
- Avoid playing the same spot again during the configured recent-history
  window.
- The software must work normally with the commercial library empty.

## On-screen graphics and sound

The Pi Zero has little graphics headroom. The safest first approach is to
pre-render 640x480 H.264 clips and play them through the same video path as the
episodes. This gives us crisp, ambitious artwork without asking the Pi to
render animation while decoding video.

Proposed graphics package:

- 1-2 second CRT wake-up and sleep clips
- Channel cards for each mode
- A Springfield station ident
- "Please stand by" recovery clip
- "Good night, Springfield" safe-shutdown clip
- Rare fake local advertisements and emergency-broadcast jokes

Any copyrighted show imagery or audio remains local. Repository artwork should
be original, licensed, or built from user-supplied assets with known rights.

## Software shape

The current scripts mix hardware access, selection, and playback in endless
top-level loops. We will separate them so most behavior can be tested on a Mac
without Raspberry Pi hardware.

```text
simpsonstv/
  app.py                    service entry point
  tv/
    catalog.py              scan and validate local media
    channels.py             channel definitions and filtering
    scheduler.py            episode/commercial ordering and recent history
    playback.py             player process and failure recovery
    controls.py             GPIO events and press patterns
    display.py              backlight/audio routing
    state.py                durable current mode and recent history
  config/
    channels.yaml           user-editable channel definitions
    episodes.yaml           curated tags and broadcast metadata
  assets/                   original, repository-safe interstitials
  tools/                    catalog and installation utilities
  tests/
```

Key implementation choices:

- Python 3 throughout.
- Pass process arguments as lists; never interpolate filenames into a shell.
- Keep the player backend behind one interface. Start with OMXPlayer for the
  existing image, but leave room for VLC or mpv on a newer Raspberry Pi OS.
- Store state in a small JSON file and update it atomically.
- Do not write playback progress continuously; protect the SD card from
  unnecessary writes.
- Treat an unplayable file as a recoverable event: log it, show the standby
  clip if appropriate, and move on.
- Use structured metadata rather than guessing special modes from titles at
  runtime.

## Metadata

Each catalog entry should eventually include:

```yaml
- id: S05E10
  title: Springfield (Or, How I Learned to Stop Worrying and Love Legalized Gambling)
  file: The Simpsons S05E10 Springfield (Or, How I Learned to Stop Worrying and Love Legalized Gambling).mp4
  air_date: 1993-12-16
  tags: [homer, springfield]
```

The catalog tool will normalize filenames such as `S03E1` to episode IDs such
as `S03E01`, report missing or duplicate episodes, and refuse to rename media
unless explicitly requested.

## Delivery plan

### Phase 0 - Safe foundation (complete)

- Preserve the original project as the `upstream` Git remote.
- Stop local `main` from pushing to upstream.
- Ignore local copyrighted media.
- Replace shell-based encoding with safe FFmpeg process arguments.
- Add filename regression tests.

### Phase 1 - Know the library

- Build a read-only catalog scanner.
- Normalize season/episode IDs in memory.
- Report the expected 226 episodes across seasons 1-10.
- Generate a starter metadata file and a human-readable audit report.
- Add the curated Treehouse of Horror tags.

**Done when:** the library can be validated without touching or renaming any
video, and S05E10 is the only current gap until its conversion completes.

### Phase 2 - Dependable channel engine

- Replace the top-level playback loop with testable catalog, scheduler, and
  playback components.
- Add recent-play avoidance and persistent channel state.
- Keep normal random playback behavior as the default.
- Add a simulated player for development on macOS.

**Done when:** automated tests prove every eligible episode is reachable,
recent episodes are avoided, and a failed file cannot stop playback.

### Phase 3 - First Easter egg

- Implement `Treehouse After Dark` from metadata tags.
- Support keyboard control on macOS and a GPIO event on the Pi.
- Create a simple pre-rendered channel card.

**Done when:** one action switches into an all-Halloween marathon, the selected
mode survives a service restart, and another action returns to normal TV.

### Phase 4 - Controls and safe shutdown

- Prototype the hidden momentary button on GPIO 27 without modifying the case.
- Add debounce, short/double/long press handling, and startup-safe defaults.
- Add the shutdown confirmation clip and system service permission.
- Document when it is safe to unplug.

**Done when:** the front knob remains unchanged, the hidden button works
reliably, and a five-second hold produces a clean shutdown.

### Phase 5 - Commercial television

- Define and validate the commercial-library manifest.
- Select commercials by episode broadcast year.
- Add duration limits, recent-ad avoidance, and an off switch.
- Test missing years and damaged files.

**Done when:** a legal local commercial collection can be added without code
changes and the TV remains functional when it is removed.

### Phase 6 - Broadcast polish

- Produce final original channel cards, idents, standby, wake, and shutdown
  clips.
- Tune transitions and perceived gap time on the actual Pi.
- Add seasonal and character channels.
- Add rare date-, sequence-, or probability-based Easter eggs.

### Phase 7 - Physical experience

- Decide hidden-button placement from an enclosure fit test.
- Update the case model only if needed.
- Finish the 1990s toy-style retail box, assembly guide, and period copy.
- Add a one-card quick-start guide explaining normal controls while keeping
  secret features secret.

## First implementation slice

The next code change should be the read-only catalog scanner and audit report.
It gives every later feature a reliable view of the library and immediately
confirms the S05E10 repair. After that, implement the channel scheduler with
`Treehouse After Dark` as its first end-to-end mode.

## Decisions to make on the physical prototype

- Hidden button under the TV versus behind/removable with the VCR
- Whether safe shutdown should be discoverable or remain an Easter egg
- Chronological versus shuffled Treehouse playback
- One commercial versus a short randomized commercial block by default
- Whether the TV should resume its previous special channel after reboot or
  always return to Springfield TV

