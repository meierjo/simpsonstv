"""Player backend and one-episode broadcast controller."""

import subprocess

from tv.state import DEFAULT_CHANNEL_ID, PlayerState


class OmxPlayerBackend:
    """Play one video with the original lightweight Raspberry Pi player."""

    def build_command(self, path):
        return ["omxplayer", "--no-osd", "--aspect-mode", "fill", str(path)]

    def play(self, episode):
        process = subprocess.Popen(self.build_command(episode.path))
        return process.wait()


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
        return episode, self.backend.play(episode)

