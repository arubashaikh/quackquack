import pygame
import random
import sys
import math
import struct

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()

WIDTH = 600
HEIGHT = 600
flappywindow = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Aruba Ka Game")
FPS = 60

GRAVITY = 0.45
FLAP_STRENGTH = -8.5
MAX_FALL_SPEED = 10
BIRD_X = 80
BIRD_RADIUS = 14
PIPE_WIDTH = 70
PIPE_GAP = 160
PIPE_SPEED = 3
PIPE_SPAWN_MS = 1400
PIPE_MIN_TOP = 60
PIPE_MAX_TOP = HEIGHT - PIPE_GAP - 150
GROUND_HEIGHT = 100

STRAWBERRY = (255, 0, 127)
MATCHA = (255, 20, 147)
PINK = (255, 0, 255)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
PURPLE = (128, 0, 128)
BLACK = (0, 0, 0)
BROWN = (139, 69, 19)
DARK_BROWN = (101, 55, 12)
GROUND_BROWN = (181, 122, 63)
CLOUD_SPEED = 0.6
CLOUD_COLOR = (255, 255, 255, 160)
HILL_TILE_WIDTH = WIDTH
HILL_AMPLITUDE = 40
HILL_BUMPS = 6
HILL_SPEED = 0.2
FAR_HILL_COLOR = (200, 0, 90)
SPARKLE_COUNT = 16
AD_DURATION_MS = 3000
BUTTON_WIDTH = 260
BUTTON_HEIGHT = 46
BUTTON_GAP = 14
BUTTON_BG = (40, 40, 40)
BUTTON_BORDER = (255, 255, 255)
BUTTON_BORDER_DISABLED = (120, 120, 120)


def build_hill_shape(tile_width, base_y, amplitude, bumps):
    points = []
    for i in range(bumps + 1):
        x = tile_width * i / bumps
        y = base_y - amplitude * (0.5 + 0.5 * math.sin(2 * math.pi * i / bumps))
        points.append((x, y))
    return points


HILL_POINTS = build_hill_shape(HILL_TILE_WIDTH, HEIGHT - GROUND_HEIGHT, HILL_AMPLITUDE, HILL_BUMPS)


class SoundManager:
    SAMPLE_RATE = 44100

    def __init__(self):
        self.enabled = True
        try:
            self.flap_sound = self._make_sweep(500, 900, 90, volume=0.35)
            self.score_sound = self._make_chime([880, 1174], 80, volume=0.4)
            self.hit_sound = self._make_noise(220, volume=0.5)
            self.click_sound = self._make_sweep(400, 300, 60, volume=0.3)
        except Exception:
            self.enabled = False

    @staticmethod
    def _envelope(i, n, fade):
        if i < fade:
            return i / fade
        if i > n - fade:
            return max(0.0, (n - i) / fade)
        return 1.0

    def _to_sound(self, samples):
        buf = bytearray()
        for s in samples:
            s = max(-32768, min(32767, int(s * 32767)))
            buf += struct.pack('<h', s)
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _make_sweep(self, start_freq, end_freq, duration_ms, volume=0.4):
        n = int(self.SAMPLE_RATE * duration_ms / 1000)
        fade = max(1, int(n * 0.1))
        phase = 0.0
        samples = []
        for i in range(n):
            freq = start_freq + (end_freq - start_freq) * (i / n)
            phase += 2 * math.pi * freq / self.SAMPLE_RATE
            amp = self._envelope(i, n, fade) * volume
            samples.append(math.sin(phase) * amp)
        return self._to_sound(samples)

    def _make_chime(self, freqs, note_ms, volume=0.4):
        n_per_note = int(self.SAMPLE_RATE * note_ms / 1000)
        fade = max(1, int(n_per_note * 0.15))
        samples = []
        for freq in freqs:
            for i in range(n_per_note):
                amp = self._envelope(i, n_per_note, fade) * volume
                samples.append(math.sin(2 * math.pi * freq * i / self.SAMPLE_RATE) * amp)
        return self._to_sound(samples)

    def _make_noise(self, duration_ms, volume=0.4):
        n = int(self.SAMPLE_RATE * duration_ms / 1000)
        samples = []
        for i in range(n):
            amp = max(0.0, 1 - i / n) * volume
            samples.append(random.uniform(-1, 1) * amp)
        return self._to_sound(samples)

    def play(self, name):
        if not self.enabled:
            return
        sound = getattr(self, f"{name}_sound", None)
        if sound:
            sound.play()

    def toggle_mute(self):
        self.enabled = not self.enabled
        return self.enabled


class Bird:
    def __init__(self):
        self.x = BIRD_X
        self.y = HEIGHT // 2
        self.velocity = 0
        self.radius = BIRD_RADIUS
        self.angle = 0

    def flap(self):
        self.velocity = FLAP_STRENGTH

    def update(self):
        self.velocity += GRAVITY
        if self.velocity > MAX_FALL_SPEED:
            self.velocity = MAX_FALL_SPEED
        self.y += self.velocity
        self.angle = max(-25, min(90, self.velocity * 4))

    def get_rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)

    def draw(self, screen):
        body = pygame.Surface((self.radius * 2 + 6, self.radius * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(body, YELLOW, (self.radius + 3, self.radius + 3), self.radius)
        pygame.draw.circle(body, BLACK, (self.radius + 3, self.radius + 3), self.radius, 2)
        pygame.draw.circle(body, WHITE, (self.radius + 9, self.radius - 2), 5)
        pygame.draw.circle(body, BLACK, (self.radius + 11, self.radius - 2), 2)
        pygame.draw.polygon(body, DARK_BROWN, [(self.radius * 2, self.radius + 2), (self.radius * 2 + 6, self.radius + 5), (self.radius * 2, self.radius + 9)])
        rotated = pygame.transform.rotate(body, -self.angle)
        rect = rotated.get_rect(center=(self.x, self.y))
        screen.blit(rotated, rect)


class Pipe:
    def __init__(self, x):
        self.x = x
        self.top_height = random.randint(PIPE_MIN_TOP, PIPE_MAX_TOP)
        self.bottom_y = self.top_height + PIPE_GAP
        self.width = PIPE_WIDTH
        self.passed = False

    def update(self):
        self.x -= PIPE_SPEED

    def off_screen(self):
        return self.x + self.width < 0

    def get_rects(self):
        top_rect = pygame.Rect(self.x, 0, self.width, self.top_height)
        bottom_rect = pygame.Rect(self.x, self.bottom_y, self.width, HEIGHT - self.bottom_y - GROUND_HEIGHT)
        return top_rect, bottom_rect

    def draw(self, screen):
        top_rect, bottom_rect = self.get_rects()
        for rect in (top_rect, bottom_rect):
            pygame.draw.rect(screen, BROWN, rect)
            pygame.draw.rect(screen, DARK_BROWN, rect, 3)
        lip_h = 24
        pygame.draw.rect(screen, DARK_BROWN, (self.x - 3, self.top_height - lip_h, self.width + 6, lip_h))
        pygame.draw.rect(screen, DARK_BROWN, (self.x - 3, self.bottom_y, self.width + 6, lip_h))


class Cloud:
    def __init__(self, x=None):
        self.x = x if x is not None else random.randint(WIDTH, WIDTH + 200)
        self.y = random.randint(30, 220)
        self.scale = random.uniform(0.7, 1.4)
        self.speed = CLOUD_SPEED * random.uniform(0.6, 1.3)
        self.puffs = []
        num_puffs = random.randint(3, 5)
        offset = 0
        for _ in range(num_puffs):
            radius = random.randint(14, 24)
            self.puffs.append((offset, random.randint(-8, 8), radius))
            offset += radius

    def update(self):
        self.x -= self.speed

    def off_screen(self):
        return self.x + 140 * self.scale < 0

    def draw(self, screen):
        cloud_surf = pygame.Surface((160, 80), pygame.SRCALPHA)
        for dx, dy, radius in self.puffs:
            r = int(radius * self.scale)
            pygame.draw.circle(cloud_surf, CLOUD_COLOR, (int(dx * self.scale) + 20, 40 + dy), r)
        screen.blit(cloud_surf, (self.x, self.y))


class Game:
    def __init__(self):
        self.screen = flappywindow
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("arial", 48, bold=True)
        self.font_med = pygame.font.SysFont("arial", 28, bold=True)
        self.font_small = pygame.font.SysFont("arial", 20)
        self.pipe_timer = pygame.USEREVENT + 1
        pygame.time.set_timer(self.pipe_timer, PIPE_SPAWN_MS)
        self.hill_scroll = 0
        self.sparkles = [{"x": random.randint(0, WIDTH), "y": random.randint(20, 260), "radius": random.randint(1, 3), "phase": random.uniform(0, math.tau), "speed": random.uniform(1.2, 2.6)} for _ in range(SPARKLE_COUNT)]
        self.high_score = 0
        self.sounds = SoundManager()
        self.reset()

    def reset(self):
        self.bird = Bird()
        self.pipes = []
        self.score = 0
        self.ground_scroll = 0
        self.game_over = False
        self.started = False
        self.watching_ad = False
        self.used_continue = False
        self.ad_start_time = 0
        self.clouds = [Cloud(x=random.randint(0, WIDTH)) for _ in range(4)]

    def spawn_pipe(self):
        self.pipes.append(Pipe(WIDTH + 20))

    def handle_flap(self):
        if self.game_over:
            return
        if not self.started:
            self.started = True
        self.bird.flap()
        self.sounds.play("flap")

    def update_background(self):
        for cloud in self.clouds:
            cloud.update()
        self.clouds = [c for c in self.clouds if not c.off_screen()]
        if random.random() < 0.01:
            self.clouds.append(Cloud())
        self.hill_scroll = (self.hill_scroll + HILL_SPEED) % HILL_TILE_WIDTH

    def update(self):
        self.update_background()
        if self.watching_ad:
            elapsed = pygame.time.get_ticks() - self.ad_start_time
            if elapsed >= AD_DURATION_MS:
                self.finish_watch_ad()
            return
        if not self.started or self.game_over:
            return
        self.bird.update()
        self.ground_scroll = (self.ground_scroll - PIPE_SPEED) % 24
        for pipe in self.pipes:
            pipe.update()
            if not pipe.passed and pipe.x + pipe.width < self.bird.x:
                pipe.passed = True
                self.score += 1
                self.sounds.play("score")
        self.pipes = [p for p in self.pipes if not p.off_screen()]
        self.check_collisions()

    def check_collisions(self):
        bird_rect = self.bird.get_rect()
        if self.bird.y + self.bird.radius >= HEIGHT - GROUND_HEIGHT:
            self.bird.y = HEIGHT - GROUND_HEIGHT - self.bird.radius
            self.end_game()
        if self.bird.y - self.bird.radius <= 0:
            self.bird.y = self.bird.radius
            self.bird.velocity = 0
        for pipe in self.pipes:
            top_rect, bottom_rect = pipe.get_rects()
            if bird_rect.colliderect(top_rect) or bird_rect.colliderect(bottom_rect):
                self.end_game()

    def end_game(self):
        if not self.game_over:
            self.game_over = True
            self.high_score = max(self.high_score, self.score)
            self.sounds.play("hit")

    def start_watch_ad(self):
        if self.used_continue or not self.game_over:
            return
        self.watching_ad = True
        self.used_continue = True
        self.ad_start_time = pygame.time.get_ticks()

    def finish_watch_ad(self):
        self.watching_ad = False
        self.game_over = False
        self.bird.y = HEIGHT // 2
        self.bird.velocity = 0
        self.bird.angle = 0
        safe_clearance = self.bird.x + 160
        self.pipes = [p for p in self.pipes if p.x > safe_clearance]

    def get_game_over_buttons(self):
        cx = WIDTH // 2
        start_y = HEIGHT // 2 + 10
        restart_rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        restart_rect.center = (cx, start_y)
        leave_rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        leave_rect.center = (cx, start_y + (BUTTON_HEIGHT + BUTTON_GAP))
        watch_ad_rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        watch_ad_rect.center = (cx, start_y + 2 * (BUTTON_HEIGHT + BUTTON_GAP))
        return {"restart": restart_rect, "leave": leave_rect, "watch_ad": watch_ad_rect}

    def draw_sun(self):
        glow = pygame.Surface((180, 180), pygame.SRCALPHA)
        center = (90, 90)
        for radius, alpha in ((80, 35), (62, 60), (44, 100), (28, 170)):
            pygame.draw.circle(glow, (255, 250, 230, alpha), center, radius)
        self.screen.blit(glow, (10, 10))

    def draw_hills(self):
        base_y = HEIGHT - GROUND_HEIGHT
        for tile in (0, 1):
            dx = -self.hill_scroll + tile * HILL_TILE_WIDTH
            ridge = [(x + dx, y) for x, y in HILL_POINTS]
            polygon = [(dx, base_y + 10)] + ridge + [(HILL_TILE_WIDTH + dx, base_y + 10)]
            pygame.draw.polygon(self.screen, FAR_HILL_COLOR, polygon)

    def draw_sparkles(self):
        t = pygame.time.get_ticks() / 1000
        for s in self.sparkles:
            alpha = int(130 + 110 * math.sin(t * s["speed"] + s["phase"]))
            alpha = max(15, min(255, alpha))
            surf = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 255, alpha), (3, 3), s["radius"])
            self.screen.blit(surf, (s["x"] - 3, s["y"] - 3))

    def draw_background(self):
        sky_bottom = HEIGHT - GROUND_HEIGHT
        for y in range(sky_bottom):
            t = y / sky_bottom
            r = STRAWBERRY[0] + (MATCHA[0] - STRAWBERRY[0]) * t
            g = STRAWBERRY[1] + (MATCHA[1] - STRAWBERRY[1]) * t
            b = STRAWBERRY[2] + (MATCHA[2] - STRAWBERRY[2]) * t
            pygame.draw.line(self.screen, (int(r), int(g), int(b)), (0, y), (WIDTH, y))
        self.draw_sun()
        self.draw_sparkles()
        self.draw_hills()
        for cloud in self.clouds:
            cloud.draw(self.screen)

    def draw_ground(self):
        ground_rect = pygame.Rect(0, HEIGHT - GROUND_HEIGHT, WIDTH, GROUND_HEIGHT)
        pygame.draw.rect(self.screen, GROUND_BROWN, ground_rect)
        pygame.draw.rect(self.screen, DARK_BROWN, (0, HEIGHT - GROUND_HEIGHT, WIDTH, 8))
        for x in range(-24, WIDTH, 24):
            pygame.draw.line(self.screen, DARK_BROWN, (x + self.ground_scroll, HEIGHT - GROUND_HEIGHT + 8), (x + self.ground_scroll + 12, HEIGHT), 4)

    def draw_text_center(self, text, font, color, y):
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(WIDTH // 2, y))
        self.screen.blit(surf, rect)

    def draw_button(self, rect, text, enabled=True):
        border_color = BUTTON_BORDER if enabled else BUTTON_BORDER_DISABLED
        pygame.draw.rect(self.screen, BUTTON_BG, rect, border_radius=10)
        pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=10)
        label = self.font_small.render(text, True, border_color)
        self.screen.blit(label, label.get_rect(center=rect.center))

    def draw_ad_overlay(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))
        elapsed = pygame.time.get_ticks() - self.ad_start_time
        remaining = max(0, (AD_DURATION_MS - elapsed) / 1000)
        self.draw_text_center("ADVERTISEMENT", self.font_med, WHITE, HEIGHT // 2 - 60)
        self.draw_text_center("(placeholder - no real ad network is wired up)", self.font_small, (200, 200, 200), HEIGHT // 2 - 24)
        self.draw_text_center(f"Resuming in {remaining:.1f}s...", self.font_small, WHITE, HEIGHT // 2 + 16)
        bar_w, bar_h = 300, 14
        progress = 1 - (remaining * 1000 / AD_DURATION_MS)
        progress = max(0.0, min(1.0, progress))
        bar_x, bar_y = WIDTH // 2 - bar_w // 2, HEIGHT // 2 + 46
        pygame.draw.rect(self.screen, (80, 80, 80), (bar_x, bar_y, bar_w, bar_h), border_radius=6)
        pygame.draw.rect(self.screen, (255, 215, 0), (bar_x, bar_y, int(bar_w * progress), bar_h), border_radius=6)

    def draw(self):
        self.draw_background()
        for pipe in self.pipes:
            pipe.draw(self.screen)
        self.draw_ground()
        self.bird.draw(self.screen)
        self.draw_text_center(str(self.score), self.font_big, WHITE, 60)
        mute_label = "M: Sound On" if self.sounds.enabled else "M: Sound Off"
        mute_surf = self.font_small.render(mute_label, True, WHITE)
        self.screen.blit(mute_surf, (WIDTH - mute_surf.get_width() - 12, 12))
        if not self.started:
            self.draw_text_center("FLAPPY BIRD", self.font_med, WHITE, HEIGHT // 2 - 60)
            self.draw_text_center("Press SPACE / Click to start", self.font_small, WHITE, HEIGHT // 2)
        elif self.watching_ad:
            self.draw_ad_overlay()
        elif self.game_over:
            self.draw_text_center("GAME OVER", self.font_big, WHITE, HEIGHT // 2 - 90)
            self.draw_text_center(f"Score: {self.score}   Best: {self.high_score}", self.font_med, WHITE, HEIGHT // 2 - 40)
            buttons = self.get_game_over_buttons()
            self.draw_button(buttons["restart"], "Restart (R)")
            self.draw_button(buttons["leave"], "Leave (Esc)")
            if self.used_continue:
                self.draw_button(buttons["watch_ad"], "No continues left", enabled=False)
            else:
                self.draw_button(buttons["watch_ad"], "Continue - Watch Ad (C)")
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == self.pipe_timer:
                    if self.started and not self.game_over:
                        self.spawn_pipe()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_UP):
                        self.handle_flap()
                    elif event.key == pygame.K_r and self.game_over and not self.watching_ad:
                        self.sounds.play("click")
                        self.reset()
                    elif event.key == pygame.K_c and self.game_over and not self.watching_ad:
                        self.sounds.play("click")
                        self.start_watch_ad()
                    elif event.key == pygame.K_m:
                        self.sounds.toggle_mute()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if self.game_over and not self.watching_ad:
                            buttons = self.get_game_over_buttons()
                            if buttons["restart"].collidepoint(event.pos):
                                self.sounds.play("click")
                                self.reset()
                            elif buttons["leave"].collidepoint(event.pos):
                                running = False
                            elif buttons["watch_ad"].collidepoint(event.pos):
                                self.sounds.play("click")
                                self.start_watch_ad()
                        elif not self.game_over and not self.watching_ad:
                            self.handle_flap()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
