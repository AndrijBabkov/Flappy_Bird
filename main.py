import pygame
import sys
import math
import random
import asyncio
import json
import os

# ── Init ──────────────────────────────────────────────────────────────────────
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

WIDTH, HEIGHT = 400, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("FLAPPY BIRD")
clock = pygame.time.Clock()

# ── High score persistence ────────────────────────────────────────────────────
HS_FILE = "highscore.json"

def load_highscore():
    try:
        with open(HS_FILE) as f:
            return json.load(f).get("hs", 0)
    except Exception:
        return 0

def save_highscore(val):
    try:
        with open(HS_FILE, "w") as f:
            json.dump({"hs": val}, f)
    except Exception:
        pass

# ── Sound synthesis ───────────────────────────────────────────────────────────
def make_sound(freq, duration, volume=0.4, wave="square"):
    try:
        import numpy as np
        sample_rate = 44100
        n = int(sample_rate * duration)
        t = np.linspace(0, duration, n, endpoint=False)
        raw = np.sin(2 * np.pi * freq * t)
        if wave == "square":
            raw = np.sign(raw)
        elif wave == "sine":
            pass  # already sine
        fade = np.linspace(1.0, 0.0, n)
        samples = (raw * fade * volume * 32767).astype(np.int16)
        stereo = np.column_stack((samples, samples))
        return pygame.sndarray.make_sound(stereo)
    except Exception:
        return pygame.mixer.Sound(buffer=bytes(44))

SND_FLAP  = make_sound(520, 0.10, wave="square")
SND_SCORE = make_sound(880, 0.15, wave="sine")
SND_DIE   = make_sound(150, 0.40, wave="square")
SND_HIT   = make_sound(220, 0.20, wave="square")

# ── Difficulty settings ───────────────────────────────────────────────────────
DIFFICULTIES = {
    "Easy":   {"speed": 2.5, "gap": 160, "label": "EASY",   "color": (80, 200, 80)},
    "Medium": {"speed": 3.2, "gap": 130, "label": "MEDIUM", "color": (220, 180, 0)},
    "Hard":   {"speed": 4.2, "gap": 105, "label": "HARD",   "color": (220, 60, 60)},
}
DIFF_KEYS = list(DIFFICULTIES.keys())

# ── Colors ────────────────────────────────────────────────────────────────────
# Day palette
DAY_SKY_TOP    = (112, 197, 255)
DAY_SKY_BOT    = (178, 230, 255)
DAY_GROUND     = (222, 184, 135)
DAY_GROUND_TOP = (110, 190, 60)
DAY_PIPE       = (88,  196, 72)
DAY_PIPE_DARK  = (58,  150, 46)
DAY_PIPE_LIGHT = (138, 226, 112)

# Night palette
NGT_SKY_TOP    = (10,  10,  40)
NGT_SKY_BOT    = (30,  30,  80)
NGT_GROUND     = (60,  50,  30)
NGT_GROUND_TOP = (30,  60,  20)
NGT_PIPE       = (30,  90,  30)
NGT_PIPE_DARK  = (10,  50,  10)
NGT_PIPE_LIGHT = (60,  130, 60)

WHITE  = (255, 255, 255)
BLACK  = (0,   0,   0)
YELLOW = (255, 215, 0)
ORANGE = (255, 140, 0)
RED    = (220, 50,  50)
BROWN  = (139, 90,  43)

# ── Layout ────────────────────────────────────────────────────────────────────
GROUND_H    = 80
GROUND_Y    = HEIGHT - GROUND_H
PIPE_W      = 60
PIPE_SPAWN_X = WIDTH + 10
BIRD_X      = 80
BIRD_W      = 38
BIRD_H      = 28
GRAVITY     = 0.45
FLAP_STR    = -7.5

# ── Asset drawing helpers ─────────────────────────────────────────────────────
def draw_gradient_rect(surface, top_color, bot_color, rect):
    """Draw a vertical gradient rectangle."""
    x, y, w, h = rect
    for i in range(h):
        ratio = i / max(h - 1, 1)
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * ratio)
        pygame.draw.line(surface, (r, g, b), (x, y + i), (x + w, y + i))

def draw_bird(surface, x, y, angle, night):
    """Draw a classic Flappy Bird style bird."""
    cx, cy = int(x), int(y)
    angle_clamped = max(-30, min(70, angle))

    # Body
    body_color  = (255, 200, 0) if not night else (200, 160, 0)
    wing_color  = (255, 160, 0) if not night else (160, 110, 0)
    eye_white   = WHITE
    eye_pupil   = BLACK
    beak_color  = ORANGE

    # Rotate surface
    bird_surf = pygame.Surface((BIRD_W + 10, BIRD_H + 10), pygame.SRCALPHA)
    bx, by = (BIRD_W + 10) // 2, (BIRD_H + 10) // 2

    # Wing (behind body)
    wing_pts = [
        (bx - 4, by + 4),
        (bx - 14, by + 12),
        (bx + 2,  by + 12),
    ]
    pygame.draw.polygon(bird_surf, wing_color, wing_pts)

    # Body (ellipse)
    pygame.draw.ellipse(bird_surf, body_color,
                        pygame.Rect(bx - BIRD_W//2, by - BIRD_H//2, BIRD_W, BIRD_H))
    pygame.draw.ellipse(bird_surf, (200, 150, 0) if not night else (140, 100, 0),
                        pygame.Rect(bx - BIRD_W//2, by - BIRD_H//2, BIRD_W, BIRD_H), 2)

    # Belly highlight
    pygame.draw.ellipse(bird_surf, (255, 230, 100) if not night else (200, 180, 80),
                        pygame.Rect(bx - 8, by, 16, 10))

    # Eye
    pygame.draw.circle(bird_surf, eye_white, (bx + 10, by - 4), 7)
    pygame.draw.circle(bird_surf, eye_pupil, (bx + 12, by - 4), 3)
    pygame.draw.circle(bird_surf, WHITE,     (bx + 13, by - 6), 1)  # glint

    # Beak
    beak_pts = [
        (bx + 16, by - 1),
        (bx + 26, by + 3),
        (bx + 16, by + 6),
    ]
    pygame.draw.polygon(bird_surf, beak_color, beak_pts)
    pygame.draw.polygon(bird_surf, ORANGE,     beak_pts, 1)

    rotated = pygame.transform.rotate(bird_surf, -angle_clamped)
    rect = rotated.get_rect(center=(cx, cy))
    surface.blit(rotated, rect)

def draw_pipe(surface, x, top_h, gap, night):
    """Draw a pair of pipes (top + bottom)."""
    pc     = DAY_PIPE       if not night else NGT_PIPE
    pc_d   = DAY_PIPE_DARK  if not night else NGT_PIPE_DARK
    pc_l   = DAY_PIPE_LIGHT if not night else NGT_PIPE_LIGHT
    cap_h  = 22
    cap_extra = 6   # cap is slightly wider

    bot_y = top_h + gap

    for is_top in (True, False):
        if is_top:
            rect   = pygame.Rect(x, 0, PIPE_W, top_h)
            cap_r  = pygame.Rect(x - cap_extra, top_h - cap_h, PIPE_W + cap_extra*2, cap_h)
        else:
            rect   = pygame.Rect(x, bot_y, PIPE_W, HEIGHT - bot_y - GROUND_H + 2)
            cap_r  = pygame.Rect(x - cap_extra, bot_y, PIPE_W + cap_extra*2, cap_h)

        # Pipe body
        pygame.draw.rect(surface, pc, rect)
        # Left shadow strip
        pygame.draw.rect(surface, pc_d,
                         pygame.Rect(rect.x, rect.y, 6, rect.h))
        # Right highlight strip
        pygame.draw.rect(surface, pc_l,
                         pygame.Rect(rect.right - 8, rect.y, 4, rect.h))
        # Cap
        pygame.draw.rect(surface, pc,   cap_r, border_radius=3)
        pygame.draw.rect(surface, pc_d,
                         pygame.Rect(cap_r.x, cap_r.y, 8, cap_r.h), border_radius=3)
        pygame.draw.rect(surface, pc_l,
                         pygame.Rect(cap_r.right - 10, cap_r.y, 5, cap_r.h), border_radius=3)

def draw_ground(surface, offset, night):
    gc  = DAY_GROUND     if not night else NGT_GROUND
    gtc = DAY_GROUND_TOP if not night else NGT_GROUND_TOP
    # Main ground
    pygame.draw.rect(surface, gc, pygame.Rect(0, GROUND_Y, WIDTH, GROUND_H))
    # Green top strip
    pygame.draw.rect(surface, gtc, pygame.Rect(0, GROUND_Y, WIDTH, 14))
    # Scrolling dirt lines
    for i in range(-1, WIDTH // 40 + 2):
        dx = (i * 40 - offset % 40)
        pygame.draw.line(surface, BROWN,
                         (dx, GROUND_Y + 20), (dx + 20, GROUND_Y + 20), 2)
        pygame.draw.line(surface, BROWN,
                         (dx + 10, GROUND_Y + 38), (dx + 30, GROUND_Y + 38), 2)

def draw_sky(surface, night, scroll):
    top = NGT_SKY_TOP if night else DAY_SKY_TOP
    bot = NGT_SKY_BOT if night else DAY_SKY_BOT
    draw_gradient_rect(surface, top, bot, (0, 0, WIDTH, GROUND_Y))

    if night:
        # Stars
        rng = random.Random(42)
        for _ in range(60):
            sx = rng.randint(0, WIDTH)
            sy = rng.randint(0, GROUND_Y - 20)
            br = rng.randint(150, 255)
            pygame.draw.circle(surface, (br, br, br), (sx, sy), 1)
        # Moon
        pygame.draw.circle(surface, (240, 240, 200), (320, 70), 22)
        pygame.draw.circle(surface, NGT_SKY_TOP,     (330, 62), 16)
    else:
        # Scrolling clouds
        cloud_rng = random.Random(7)
        for i in range(5):
            cx = int((cloud_rng.randint(0, WIDTH) - scroll * 0.3) % WIDTH)
            cy = cloud_rng.randint(40, 200)
            for ox, oy, r in [(0,0,22),(20,-10,18),(-20,-8,16),(38,2,14),(-38,4,13)]:
                pygame.draw.circle(surface, (255,255,255), (cx+ox, cy+oy), r)

# ── Pipe manager ──────────────────────────────────────────────────────────────
class PipeManager:
    def __init__(self, speed, gap):
        self.speed  = speed
        self.gap    = gap
        self.pipes  = []   # list of [x, top_h, scored]
        self.timer  = 0
        self.interval = 90  # frames between pipes

    def update(self):
        self.timer += 1
        if self.timer >= self.interval:
            self.timer = 0
            top_h = random.randint(60, GROUND_Y - self.gap - 60)
            self.pipes.append([float(PIPE_SPAWN_X), top_h, False])

        for p in self.pipes:
            p[0] -= self.speed
        self.pipes = [p for p in self.pipes if p[0] > -PIPE_W - 20]

    def draw(self, surface, night):
        for p in self.pipes:
            draw_pipe(surface, int(p[0]), p[1], self.gap, night)

    def check_score(self, bird_x):
        scored = False
        for p in self.pipes:
            if not p[2] and p[0] + PIPE_W < bird_x:
                p[2] = True
                scored = True
        return scored

    def check_collision(self, bird_x, bird_y, bird_r=13):
        for p in self.pipes:
            px, top_h = p[0], p[1]
            bot_y = top_h + self.gap
            cap_extra = 6
            # top pipe rect (including cap)
            top_rect = pygame.Rect(px - cap_extra, 0,
                                   PIPE_W + cap_extra * 2, top_h)
            bot_rect = pygame.Rect(px - cap_extra, bot_y,
                                   PIPE_W + cap_extra * 2, HEIGHT)
            bird_rect = pygame.Rect(bird_x - bird_r, bird_y - bird_r,
                                    bird_r * 2, bird_r * 2)
            if bird_rect.colliderect(top_rect) or bird_rect.colliderect(bot_rect):
                return True
        return False

# ── Main Game ─────────────────────────────────────────────────────────────────
class FlappyGame:
    def __init__(self):
        self.font_huge  = pygame.font.SysFont("arial", 64, bold=True)
        self.font_big   = pygame.font.SysFont("arial", 40, bold=True)
        self.font_med   = pygame.font.SysFont("arial", 26, bold=True)
        self.font_small = pygame.font.SysFont("arial", 18)

        self.highscore  = load_highscore()
        self.diff_idx   = 1  # default Medium
        self.reset()

    def reset(self):
        diff = DIFFICULTIES[DIFF_KEYS[self.diff_idx]]
        self.pipes      = PipeManager(diff["speed"], diff["gap"])
        self.bird_y     = float(HEIGHT // 2)
        self.bird_vel   = 0.0
        self.bird_angle = 0.0
        self.score      = 0
        self.ground_off = 0.0
        self.scroll     = 0.0
        self.alive      = True
        self.started    = False
        self.night      = False
        self.night_timer = 0
        self.state      = "title"  # title | playing | dead

    def go_to_title(self):
        self.reset()
        self.state = "title"

    def flap(self, from_mouse=False):
        if self.state == "title":
            # Transition to playing — but don't also flap if triggered by mouse,
            # so the bird doesn't instantly launch the moment the screen changes.
            self.state   = "playing"
            self.started = True
            if not from_mouse:
                self.bird_vel = FLAP_STR
                SND_FLAP.play()
        elif self.state == "playing" and self.alive:
            self.bird_vel = FLAP_STR
            SND_FLAP.play()
        elif self.state == "dead":
            self.reset()
            self.state   = "playing"
            self.started = True
            if not from_mouse:
                self.bird_vel = FLAP_STR
                SND_FLAP.play()

    def update(self):
        diff_speed = DIFFICULTIES[DIFF_KEYS[self.diff_idx]]["speed"]
        self.scroll += diff_speed * 0.3

        if self.state == "title":
            # Bird hovering animation on title
            self.bird_y   = HEIGHT // 2 + math.sin(pygame.time.get_ticks() * 0.003) * 12
            self.bird_vel = math.cos(pygame.time.get_ticks() * 0.003) * 0.5
            self.ground_off += diff_speed
            return

        if self.state == "dead":
            # Let bird fall to ground after death
            self.bird_vel   += GRAVITY * 1.5
            self.bird_y     += self.bird_vel
            self.bird_angle  = 90
            if self.bird_y >= GROUND_Y - 14:
                self.bird_y = float(GROUND_Y - 14)
            return

        # Playing
        self.bird_vel   += GRAVITY
        self.bird_y     += self.bird_vel
        self.bird_angle  = self.bird_vel * 4.5

        self.ground_off += diff_speed
        self.pipes.update()

        # Score
        if self.pipes.check_score(BIRD_X + BIRD_W // 2):
            self.score += 1
            SND_SCORE.play()
            if self.score > self.highscore:
                self.highscore = self.score
                save_highscore(self.highscore)

        # Day/night toggle every 10 points
        self.night_timer = self.score // 10
        self.night = (self.night_timer % 2 == 1)

        # Collision with ground or ceiling
        if self.bird_y >= GROUND_Y - 14:
            self.bird_y = float(GROUND_Y - 14)
            self._die()
        elif self.bird_y <= 14:
            self.bird_y = 14
            self._die()

        # Pipe collision
        if self.pipes.check_collision(BIRD_X + BIRD_W // 2 - 4,
                                      int(self.bird_y), bird_r=12):
            self._die()

    def _die(self):
        if self.state == "playing":
            SND_HIT.play()
            pygame.time.delay(80)
            SND_DIE.play()
            self.state = "dead"

    def draw(self):
        # Sky
        draw_sky(screen, self.night, int(self.scroll))
        # Pipes
        self.pipes.draw(screen, self.night)
        # Ground
        draw_ground(screen, self.ground_off, self.night)
        # Bird
        draw_bird(screen, BIRD_X + BIRD_W // 2, self.bird_y,
                  self.bird_angle, self.night)

        if self.state == "title":
            self._draw_title()
        elif self.state == "playing":
            self._draw_hud()
        elif self.state == "dead":
            self._draw_hud()
            self._draw_death_panel()

        pygame.display.flip()

    def _draw_hud(self):
        # Score (big white with black outline)
        score_str = str(self.score)
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2)]:
            s = self.font_huge.render(score_str, True, BLACK)
            screen.blit(s, s.get_rect(center=(WIDTH // 2 + dx, 80 + dy)))
        s = self.font_huge.render(score_str, True, WHITE)
        screen.blit(s, s.get_rect(center=(WIDTH // 2, 80)))

        # Difficulty badge
        diff = DIFFICULTIES[DIFF_KEYS[self.diff_idx]]
        badge = self.font_small.render(diff["label"], True, WHITE)
        br = badge.get_rect(topright=(WIDTH - 10, 10))
        pygame.draw.rect(screen, diff["color"], br.inflate(12, 6), border_radius=4)
        screen.blit(badge, br)

    def _draw_title(self):
        # Title panel
        panel = pygame.Rect(WIDTH // 2 - 170, 120, 340, 200)
        pygame.draw.rect(screen, (255, 255, 255, 0), panel)

        # Shadow + title text
        for dx, dy in [(-3, 3)]:
            t = self.font_big.render("FLAPPY BIRD", True, (80, 50, 0))
            screen.blit(t, t.get_rect(center=(WIDTH // 2 + dx, 160 + dy)))
        t = self.font_big.render("FLAPPY BIRD", True, YELLOW)
        screen.blit(t, t.get_rect(center=(WIDTH // 2, 160)))

        # Difficulty selector
        diff = DIFFICULTIES[DIFF_KEYS[self.diff_idx]]
        pygame.draw.rect(screen, (0, 0, 0, 128),
                         pygame.Rect(WIDTH // 2 - 130, 200, 260, 80),
                         border_radius=10)
        pygame.draw.rect(screen, WHITE,
                         pygame.Rect(WIDTH // 2 - 130, 200, 260, 80),
                         2, border_radius=10)

        d_label = self.font_med.render("DIFFICULTY", True, WHITE)
        screen.blit(d_label, d_label.get_rect(center=(WIDTH // 2, 218)))

        # Arrows + current
        arrow_l = self.font_med.render("<", True, WHITE)
        arrow_r = self.font_med.render(">", True, WHITE)
        d_name  = self.font_med.render(diff["label"], True, diff["color"])
        screen.blit(arrow_l, arrow_l.get_rect(center=(WIDTH // 2 - 80, 250)))
        screen.blit(d_name,  d_name.get_rect(center=(WIDTH // 2, 250)))
        screen.blit(arrow_r, arrow_r.get_rect(center=(WIDTH // 2 + 80, 250)))

        # High score
        hs_txt = self.font_small.render(f"Best: {self.highscore}", True, YELLOW)
        screen.blit(hs_txt, hs_txt.get_rect(center=(WIDTH // 2, 300)))

        # Tap to start
        pulse = int(200 + 55 * math.sin(pygame.time.get_ticks() * 0.004))
        tap = self.font_med.render("TAP / SPACE to start", True, (pulse, pulse, pulse))
        screen.blit(tap, tap.get_rect(center=(WIDTH // 2, 490)))

        # Controls hint
        hint = self.font_small.render("← → difficulty  |  ESC = menu", True, (180, 180, 180))
        screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 520)))

    def _draw_death_panel(self):
        # Dim overlay
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 120))
        screen.blit(ov, (0, 0))

        # Panel
        panel = pygame.Rect(WIDTH // 2 - 145, HEIGHT // 2 - 120, 290, 230)
        pygame.draw.rect(screen, (240, 220, 160), panel, border_radius=12)
        pygame.draw.rect(screen, (180, 140, 60),  panel, 3,  border_radius=12)

        # Game Over text
        go = self.font_big.render("GAME OVER", True, RED)
        screen.blit(go, go.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 85)))

        # Score row
        sc_label = self.font_med.render("SCORE", True, BROWN)
        sc_val   = self.font_med.render(str(self.score), True, BLACK)
        screen.blit(sc_label, sc_label.get_rect(midleft=(WIDTH // 2 - 100, HEIGHT // 2 - 30)))
        screen.blit(sc_val,   sc_val.get_rect(midright=(WIDTH // 2 + 110, HEIGHT // 2 - 30)))

        # Best row
        new_best = self.score >= self.highscore and self.score > 0
        hs_color = (200, 50, 50) if new_best else BROWN
        hs_label = self.font_med.render("BEST", True, hs_color)
        hs_val   = self.font_med.render(str(self.highscore), True, BLACK)
        screen.blit(hs_label, hs_label.get_rect(midleft=(WIDTH // 2 - 100, HEIGHT // 2 + 5)))
        screen.blit(hs_val,   hs_val.get_rect(midright=(WIDTH // 2 + 110, HEIGHT // 2 + 5)))
        if new_best:
            nb = self.font_small.render("NEW BEST!", True, (200, 50, 50))
            screen.blit(nb, nb.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 28)))

        # Divider
        pygame.draw.line(screen, (180, 140, 60),
                         (panel.x + 15, HEIGHT // 2 + 42),
                         (panel.right - 15, HEIGHT // 2 + 42), 2)

        # Restart hint
        pulse = int(180 + 75 * math.sin(pygame.time.get_ticks() * 0.005))
        restart = self.font_small.render("TAP/SPACE restart  |  ESC = menu", True, (pulse, 80, 0))
        screen.blit(restart, restart.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 70)))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w,
                             pygame.K_RETURN):
                self.flap(from_mouse=False)
            if event.key == pygame.K_ESCAPE and self.state != "title":
                self.go_to_title()
                return
            if event.key == pygame.K_LEFT and self.state == "title":
                self.diff_idx = (self.diff_idx - 1) % len(DIFF_KEYS)
                self.reset()
                self.state = "title"
            if event.key == pygame.K_RIGHT and self.state == "title":
                self.diff_idx = (self.diff_idx + 1) % len(DIFF_KEYS)
                self.reset()
                self.state = "title"

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check arrow clicks on title
            if self.state == "title":
                mx, my = event.pos
                if 200 <= my <= 270:
                    if mx < WIDTH // 2 - 30:
                        self.diff_idx = (self.diff_idx - 1) % len(DIFF_KEYS)
                        self.reset(); self.state = "title"; return
                    elif mx > WIDTH // 2 + 30:
                        self.diff_idx = (self.diff_idx + 1) % len(DIFF_KEYS)
                        self.reset(); self.state = "title"; return
            self.flap(from_mouse=True)

# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    game = FlappyGame()
    while True:
        for event in pygame.event.get():
            game.handle_event(event)
        game.update()
        game.draw()
        clock.tick(60)
        await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main())
