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

### Hidden touch controls

No additional button or case modification is planned. The Waveshare display
already provides five-point capacitive touch over I2C, so the glass becomes a
secret control surface while normal playback remains visually uncluttered.

- **One-finger hold for 2 seconds:** open the hidden channel overlay. This is
  dependable on the small display while remaining unlikely during normal use.
- **Tap a channel card:** change channels and briefly show its broadcast ident.
- **Swipe left or right:** browse the available special channels.
- **Tap the currently active channel:** close the overlay and return to the
  broadcast.
- **Inactivity:** close the overlay automatically after 10 seconds.

The touch UI must use large targets and work without text entry. A keyboard
and mouse simulator will provide the same events during development on macOS.

### Safe shutdown

Safe shutdown belongs inside the hidden touch overlay as a large "GOOD NIGHT,
SPRINGFIELD" control. Holding it for one second begins shutdown; a short
tap does nothing beyond filling a visible progress ring. The final clip tells
the user when the Pi may be unplugged.

This is useful because abruptly removing power can corrupt a Linux SD card,
especially during a write. It is not a launch blocker: the software will also
minimize state writes and use atomic replacement so ordinary real-world
unplugging is less risky. The front latching knob will retain the original
screen-and-audio behavior and will not shut down the Pi.

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

### Phase 1 - Know the library (complete)

- Build a read-only catalog scanner.
- Normalize season/episode IDs in memory.
- Report the expected 226 episodes across seasons 1-10.
- Generate a starter metadata file and a human-readable audit report.
- Add the curated Treehouse of Horror tags.

**Result:** the read-only audit recognizes all 226 expected episodes, including
the restored S05E10, with no missing episodes, duplicates, unexpected IDs, or
unrecognized filenames. Starter metadata tags all nine Treehouse of Horror
episodes from seasons 2-10.

### Phase 2 - Dependable channel engine

- Replace the top-level playback loop with testable catalog, scheduler, and
  playback components.
- Add recent-play avoidance and persistent channel state.
- Keep normal random playback behavior as the default.
- Add a simulated player for development on macOS.

**Done when:** automated tests prove every eligible episode is reachable,
recent episodes are avoided, and a failed file cannot stop playback.

### Phase 3 - First Easter egg and touch controls

- Implement `Treehouse After Dark` from metadata tags.
- Read touch events from the existing Waveshare capacitive panel.
- Add the one-finger hold and a keyboard/mouse equivalent on macOS.
- Build a large-target channel overlay that disappears automatically.
- Create a simple pre-rendered channel card.

**Done when:** the hidden overlay switches into an all-Halloween marathon, the
selected mode survives a service restart, and normal playback has no permanent
on-screen controls.

### Phase 4 - Safe shutdown and touch polish

- Tune touch rotation, hit areas, gesture timing, and startup-safe defaults on
  the actual display.
- Add the shutdown confirmation clip and system service permission.
- Document when it is safe to unplug.

**Done when:** the front knob remains unchanged, accidental shutdown is
impractical, and a one-second on-screen hold produces a clean shutdown.

### Phase 5 - Commercial television

- [x] Define and validate the commercial-library manifest.
- [x] Select commercials by episode broadcast year.
- [x] Add review approval, recent-ad avoidance, and an off switch.
- [x] Test missing years and absent files.

**Result:** approved exact-year commercials and sponsor bumpers are optional
preroll. The TV remains functional when the collection is missing or a clip
fails, and `config/commercials.json` can disable the feature without code
changes.

### Phase 6 - Broadcast polish

- Produce final original channel cards, idents, standby, wake, and shutdown
  clips.
- Curate post-opening commercial cue points; uncued episodes retain safe
  preroll rather than using a guessed universal timestamp.
- Tune transitions and perceived gap time on the actual Pi.
- Add seasonal and character channels.
- Add rare date-, sequence-, or probability-based Easter eggs.

### Phase 7 - Physical experience

- Confirm that the existing screen opening permits comfortable use of every
  touch target near the bezel.
- Avoid case changes or additional controls unless testing finds a genuine
  usability problem that software cannot solve.
- Finish the 1990s toy-style retail box, assembly guide, and period copy.
- Add a one-card quick-start guide explaining normal controls while keeping
  secret features secret.

## First implementation slice

The next code change should be the channel scheduler with recent-play
avoidance. `Treehouse After Dark` will be its first end-to-end special mode,
using the curated metadata rather than title matching.

## Decisions to make on the physical prototype

- Whether safe shutdown should be shown in the channel overlay or one level
  deeper to prevent accidents
- Whether the hold should work anywhere or only inside a generous secret zone
- Chronological versus shuffled Treehouse playback
- One commercial versus a short randomized commercial block by default
- Whether the TV should resume its previous special channel after reboot or
  always return to Springfield TV

