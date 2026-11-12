"""Player backend and one-episode broadcast controller."""

import os
import signal
import subprocess
import time

from tv.breaks import break_cue_for_episode, format_omx_position
from tv.commercials import broadcast_year_for_episode
from tv.state import DEFAULT_CHANNEL_ID, PlayerState


class OmxPlayerBackend:
    """Play one video with the original lightweight Raspberry Pi player."""

    def build_command(self, path, start_at=None):
        command = ["omxplayer", "--no-osd", "--aspect-mode", "fill"]
        if start_at is not None and start_at > 0:
            command.extend(["--pos", format_omx_position(start_at)])
        command.append(str(path))
        return command

    def play(self, episode, should_stop=None, start_at=None, stop_after=None):
        # OMXPlayer may launch omxplayer.bin as a child. Give the complete
        # player tree its own process group so a channel change cannot leave
        # the decoder child running behind the next episode.
        process = subprocess.Popen(
            self.build_command(episode.path, start_at=start_at),
            start_new_session=True,
        )
        started_at = time.monotonic()
        while process.poll() is None:
            if should_stop is not None and should_stop():
                self._stop_process_group(process)
                return 0
            if stop_after is not None and time.monotonic() - started_at >= stop_after:
                self._stop_process_group(process)
                return 0
            time.sleep(0.25)
        return process.returncode

    def _stop_process_group(self, process):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


class PlaybackController:
    """Select and play one episode using the latest persisted channel."""

    def __init__(
        self,
        channels,
        scheduler,
        state_store,
        backend,
        commercial_scheduler=None,
        episode_metadata=None,
        broadcast_years=None,
        break_cues=None,
        suppress_initial_preroll=True,
    ):
        self.channels = channels
        self.scheduler = scheduler
        self.state_store = state_store
        self.backend = backend
        self.commercial_scheduler = commercial_scheduler
        self.episode_metadata = episode_metadata or {}
        self.broadcast_years = broadcast_years or {}
        self.break_cues = break_cues or {}
        self._initial_broadcast_pending = bool(suppress_initial_preroll)

    def play_next(self):
        state = self.state_store.load()
        channel = self.channels.get(state.channel_id)
        if channel is None:
            channel = self.channels[DEFAULT_CHANNEL_ID]

        episode = self.scheduler.choose_next(channel)
        self.state_store.save(
            PlayerState(channel.channel_id, self.scheduler.recent_ids, state.menu_open)
        )
        selected_channel_id = channel.channel_id

        def channel_changed():
            latest_state = self.state_store.load()
            return latest_state.menu_open or latest_state.channel_id != selected_channel_id

        preroll = ()
        if self.commercial_scheduler is not None:
            year = broadcast_year_for_episode(
                episode, self.episode_metadata, self.broadcast_years
            )
            preroll = self.commercial_scheduler.choose_preroll(year)

        cue = break_cue_for_episode(episode, self.break_cues)
        if self._initial_broadcast_pending and cue is None:
            # A cold boot should look like a television coming to life, not an
            # advertisement player. Reviewed cues are different: the episode
            # opening is shown before its first commercial.
            preroll = ()
        if cue is not None and preroll:
            print("Playing opening of %s to %.1f seconds" % (episode.episode_id, cue), flush=True)
            return_code = self.backend.play(
                episode, should_stop=channel_changed, stop_after=cue
            )
            if channel_changed():
                return episode, 0
            if return_code:
                return episode, return_code
            self._initial_broadcast_pending = False

        for clip in preroll:
            print(
                "Playing %s for %d: %s" % (clip.kind, clip.year, clip.path.name),
                flush=True,
            )
            return_code = self.backend.play(clip, should_stop=channel_changed)
            if channel_changed():
                return episode, 0
            if return_code:
                print(
                    "Skipping failed preroll %s (status %s)"
                    % (clip.path.name, return_code),
                    flush=True,
                )

        print(
            "%s %s - %s [%s]"
            % (
                "Resuming" if cue is not None and preroll else "Playing",
                episode.episode_id,
                episode.title,
                channel.name,
            ),
            flush=True,
        )
        self._initial_broadcast_pending = False
        return episode, self.backend.play(
            episode,
            should_stop=channel_changed,
            start_at=cue if cue is not None and preroll else None,
        )

