"""Player backend and one-episode broadcast controller."""

import os
import signal
import subprocess
import time

from tv.commercials import broadcast_year_for_episode
from tv.state import DEFAULT_CHANNEL_ID, PlayerState


class OmxPlayerBackend:
    """Play one video with the original lightweight Raspberry Pi player."""

    def build_command(self, path):
        return ["omxplayer", "--no-osd", "--aspect-mode", "fill", str(path)]

    def play(self, episode, should_stop=None):
        # OMXPlayer may launch omxplayer.bin as a child. Give the complete
        # player tree its own process group so a channel change cannot leave
        # the decoder child running behind the next episode.
        process = subprocess.Popen(
            self.build_command(episode.path),
            start_new_session=True,
        )
        while process.poll() is None:
            if should_stop is not None and should_stop():
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
    ):
        self.channels = channels
        self.scheduler = scheduler
        self.state_store = state_store
        self.backend = backend
        self.commercial_scheduler = commercial_scheduler
        self.episode_metadata = episode_metadata or {}
        self.broadcast_years = broadcast_years or {}

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

        if self.commercial_scheduler is not None:
            year = broadcast_year_for_episode(
                episode, self.episode_metadata, self.broadcast_years
            )
            for clip in self.commercial_scheduler.choose_preroll(year):
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
            "Playing %s - %s [%s]"
            % (episode.episode_id, episode.title, channel.name),
            flush=True,
        )
        return episode, self.backend.play(episode, should_stop=channel_changed)

