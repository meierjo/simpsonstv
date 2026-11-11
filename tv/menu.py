"""Lightweight 640x480 channel menu for the Raspberry Pi framebuffer."""

import os


WIDTH = 640
HEIGHT = 480
LEFT_CARD = (28, 112, 278, 260)
RIGHT_CARD = (334, 112, 278, 260)


def channel_at(position):
    """Return the channel ID at a display coordinate, or ``None``."""
    x, y = position
    if _contains(LEFT_CARD, x, y):
        return "springfield-tv"
    if _contains(RIGHT_CARD, x, y):
        return "treehouse-after-dark"
    return None


def _contains(rectangle, x, y):
    left, top, width, height = rectangle
    return left <= x < left + width and top <= y < top + height


class PygameChannelMenu:
    """Draw the channel selector directly on the primary framebuffer."""

    def __init__(self):
        os.environ.setdefault("SDL_FBDEV", "/dev/fb0")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("SDL_NOMOUSE", "1")
        try:
            import pygame
        except ImportError:
            raise RuntimeError(
                "Channel menu requires pygame: sudo apt-get install python3-pygame"
            )
        self.pygame = pygame
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)

    def show(self, active_channel_id):
        pygame = self.pygame
        self.screen.fill((39, 20, 73))
        pygame.draw.rect(self.screen, (247, 196, 54), (0, 0, WIDTH, 18))
        pygame.draw.rect(self.screen, (40, 191, 190), (0, 18, WIDTH, 10))
        pygame.draw.rect(self.screen, (236, 83, 146), (0, 28, WIDTH, 7))

        self._center_text("CHOOSE YOUR CHANNEL", 58, 46, (255, 246, 197))
        self._draw_card(
            LEFT_CARD,
            "CHANNEL 6",
            "SPRINGFIELD TV",
            "ALL EPISODES",
            (42, 176, 195),
            active_channel_id == "springfield-tv",
        )
        self._draw_card(
            RIGHT_CARD,
            "AFTER DARK",
            "TREEHOUSE",
            "HALLOWEEN",
            (210, 73, 139),
            active_channel_id == "treehouse-after-dark",
        )
        self._center_text("TAP A CHANNEL  -  WAIT TO CANCEL", 430, 25, (223, 214, 235))
        pygame.display.flip()

    def close(self):
        self.screen.fill((0, 0, 0))
        self.pygame.display.flip()
        self.pygame.display.quit()
        self.pygame.font.quit()

    def _draw_card(self, rectangle, eyebrow, title, subtitle, color, active):
        pygame = self.pygame
        border = (255, 226, 85) if active else (238, 230, 245)
        border_width = 10 if active else 5
        pygame.draw.rect(self.screen, (16, 10, 31), rectangle)
        inset = (
            rectangle[0] + 8,
            rectangle[1] + 8,
            rectangle[2] - 16,
            rectangle[3] - 16,
        )
        pygame.draw.rect(self.screen, color, inset)
        pygame.draw.rect(self.screen, border, rectangle, border_width)
        center_x = rectangle[0] + rectangle[2] // 2
        self._text(eyebrow, center_x, rectangle[1] + 42, 28, (24, 13, 42))
        self._text(title, center_x, rectangle[1] + 105, 42, (255, 248, 216))
        self._text(subtitle, center_x, rectangle[1] + 188, 25, (24, 13, 42))
        if active:
            self._text("ON AIR", center_x, rectangle[1] + 225, 24, (255, 226, 85))

    def _center_text(self, text, y, size, color):
        self._text(text, WIDTH // 2, y, size, color)

    def _text(self, text, center_x, y, size, color):
        font = self.pygame.font.Font(None, size)
        surface = font.render(text, True, color)
        rectangle = surface.get_rect(center=(center_x, y))
        self.screen.blit(surface, rectangle)

