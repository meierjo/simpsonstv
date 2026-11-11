"""Player backend and one-episode broadcast controller."""

import subprocess
import time

from tv.state import DEFAULT_CHANNEL_ID, PlayerState


class OmxPlayerBackend:
    """Play one video with the original lightweight Raspberry Pi player."""

    def build_command(self, path):
        return ["omxplayer", "--no-osd", "--aspect-mode", "fill", str(path)]

    def play(self, episode, should_stop=None):
        process = subprocess.Popen(self.build_command(episode.path))
        while process.poll() is None:
            if should_stop is not None and should_stop():
                process.terminate()
                process.wait()
                return 0
            time.sleep(0.25)
        return process.returncode


class PlaybackController:
    """Select and play one episode using the latest persisted channel."""

    def __init__(self, channels, scheduler, state_store, backend):
        self.channels = channels
        self.scheduler = scheduler
        self.state_store = state_store
        self.backend = backend

    def play_next(self):
        state = self.state_store.load()
        channel = self.channels.get(state.channel_id)
        if channel is None:
            channel = self.channels[DEFAULT_CHANNEL_ID]

        episode = self.scheduler.choose_next(channel)
        self.state_store.save(PlayerState(channel.channel_id, self.scheduler.recent_ids))
        print(
            "Playing %s - %s [%s]"
            % (episode.episode_id, episode.title, channel.name),
            flush=True,
        )
        selected_channel_id = channel.channel_id

        def channel_changed():
            return self.state_store.load().channel_id != selected_channel_id

        return episode, self.backend.play(episode, should_stop=channel_changed)

