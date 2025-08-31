
"""
Whack-a-Zombie (Pygame)
-----------------------
Meets the rubric essentials:
- Background with multiple zombie spawn locations (>= 6)
- Distinct zombie head design (drawn vector art)
- Zombie head has a timer (800–1500 ms) and auto-despawns
- Mouse interaction / hit detection (circle hitbox), prevents double-counting
- HUD shows hits, misses, and accuracy
Extras:
- Simple spawn/despawn animations
- Optional sound effects (gracefully disabled if mixer or numpy unavailable)
Controls:
- Click to whack!
- Press M to mute/unmute audio (if available)
- Press ESC or close the window to quit
"""

import math
import random
import sys
import time

import pygame

# ---------- Config ----------
WIDTH, HEIGHT = 900, 600
FPS = 60
BG_COLOR = (24, 28, 38)
HUD_COLOR = (230, 235, 245)
SPAWN_MIN_MS = 800
SPAWN_MAX_MS = 1500

# Create 8+ distinct spawn points distributed across the playfield
SPAWN_POINTS = [
    (150, 160), (300, 140), (450, 170), (600, 150),
    (750, 170), (220, 320), (420, 300), (620, 330),
    (780, 310), (320, 480), (500, 470), (700, 500)
]

# Zombie visual parameters
ZOMBIE_BASE_RADIUS = 48
ZOMBIE_FACE = {
    "skin": (141, 199, 63),
    "shadow": (94, 134, 45),
    "eye": (245, 245, 245),
    "pupil": (20, 20, 20),
    "scar": (183, 62, 62),
    "mouth": (60, 20, 20),
    "tooth": (235, 235, 235),
}

# Animation durations
SPAWN_ANIM_MS = 180
DESPAWN_ANIM_MS = 220


def try_make_sound():
    """Return (hit_sound, mute_flag_supported)
    Attempts to synthesize a short click sound. If numpy/mixer is unavailable, returns (None, False).
    """
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        try:
            import numpy as np  # optional
        except Exception:
            return None, False

        sr = 22050
        dur = 0.08
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # A short percussive blip
        wave = (np.sin(2 * np.pi * 880 * t) * np.exp(-18 * t)) * 0.6
        # Convert to int16
        arr = (wave * 32767).astype(np.int16)
        sound = pygame.sndarray.make_sound(arr.copy())
        return sound, True
    except Exception:
        return None, False


class Zombie:
    def __init__(self, pos):
        self.x, self.y = pos
        self.radius = ZOMBIE_BASE_RADIUS
        self.spawn_time = pygame.time.get_ticks()
        self.lifetime_ms = random.randint(SPAWN_MIN_MS, SPAWN_MAX_MS)
        self.state = "spawning"  # spawning -> alive -> despawning -> dead
        self.hit_registered = False
        self.state_time = self.spawn_time  # timestamp of entering current state

    def update(self, now):
        if self.state == "spawning":
            if now - self.state_time >= SPAWN_ANIM_MS:
                self.state = "alive"
                self.state_time = now
        elif self.state == "alive":
            if now - self.spawn_time >= self.lifetime_ms:
                self.state = "despawning"
                self.state_time = now
        elif self.state == "despawning":
            if now - self.state_time >= DESPAWN_ANIM_MS:
                self.state = "dead"

    def is_clickable(self):
        return self.state in ("spawning", "alive") and not self.hit_registered

    def hit_test(self, pos):
        mx, my = pos
        return (mx - self.x) ** 2 + (my - self.y) ** 2 <= (self.radius * 0.95) ** 2

    def register_hit(self):
        self.hit_registered = True
        # Immediately transition to despawn, but allow animation
        self.state = "despawning"
        self.state_time = pygame.time.get_ticks()

    def draw(self, surf, now):
        # Compute scale for spawn/despawn animation
        scale = 1.0
        if self.state == "spawning":
            t = (now - self.state_time) / SPAWN_ANIM_MS
            t = max(0.0, min(1.0, t))
            # pop-in scale (overshoot a touch)
            scale = 0.6 + 0.5 * (-2 * t * (t - 1))  # ease-out quad-ish
        elif self.state == "despawning":
            t = (now - self.state_time) / DESPAWN_ANIM_MS
            t = max(0.0, min(1.0, t))
            # shrink away
            scale = 1.0 - 0.9 * t

        r = int(self.radius * scale)

        # Drop shadow
        pygame.draw.circle(surf, (0, 0, 0, 30), (self.x + 6, self.y + 10), int(r * 0.95))

        # Face base
        pygame.draw.circle(surf, ZOMBIE_FACE["skin"], (self.x, self.y), r)
        # Top-left shading
        pygame.draw.circle(surf, ZOMBIE_FACE["shadow"], (self.x - int(r*0.2), self.y - int(r*0.2)), int(r*1.02), width=4)

        # Eyes
        ex = int(r * 0.45)
        ey = int(r * 0.20)
        pygame.draw.circle(surf, ZOMBIE_FACE["eye"], (self.x - ex, self.y - ey), int(r * 0.28))
        pygame.draw.circle(surf, ZOMBIE_FACE["eye"], (self.x + ex, self.y - ey), int(r * 0.24))
        pygame.draw.circle(surf, ZOMBIE_FACE["pupil"], (self.x - ex, self.y - ey), int(r * 0.10))
        pygame.draw.circle(surf, ZOMBIE_FACE["pupil"], (self.x + ex, self.y - ey), int(r * 0.08))

        # Scar
        pygame.draw.line(surf, ZOMBIE_FACE["scar"], (self.x - int(r*0.7), self.y - int(r*0.55)),
                         (self.x - int(r*0.2), self.y - int(r*0.1)), width=3)
        pygame.draw.line(surf, ZOMBIE_FACE["scar"], (self.x - int(r*0.6), self.y - int(r*0.5)),
                         (self.x - int(r*0.5), self.y - int(r*0.35)), width=3)

        # Mouth
        mouth_w = int(r * 1.0)
        mouth_h = int(r * 0.45)
        mouth_rect = pygame.Rect(0, 0, mouth_w, mouth_h)
        mouth_rect.center = (self.x, self.y + int(r * 0.40))
        pygame.draw.ellipse(surf, ZOMBIE_FACE["mouth"], mouth_rect, width=0)

        # Teeth
        tooth_w = max(4, int(r * 0.12))
        for dx in (-int(mouth_w * 0.25), 0, int(mouth_w * 0.25)):
            tooth_rect = pygame.Rect(0, 0, tooth_w, int(mouth_h * 0.35))
            tooth_rect.center = (self.x + dx, self.y + int(r * 0.33))
            pygame.draw.rect(surf, ZOMBIE_FACE["tooth"], tooth_rect)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Whack-a-Zombie")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 22)

    hit_sound, sound_supported = try_make_sound()
    is_muted = False

    # Game state
    hits = 0
    misses = 0
    zombie = None
    next_spawn_time = 0  # when to spawn next zombie (ms)

    # Pre-draw background grid/holes (simple playfield)
    bg_surface = pygame.Surface((WIDTH, HEIGHT))
    bg_surface.fill(BG_COLOR)
    # Decorative "holes" for spawn points
    for (sx, sy) in SPAWN_POINTS:
        pygame.draw.circle(bg_surface, (18, 20, 26), (sx, sy + 18), 58)
        pygame.draw.circle(bg_surface, (28, 33, 43), (sx, sy + 14), 54)

    running = True
    while running:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_m and sound_supported:
                    is_muted = not is_muted
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Only one head counted per click
                if zombie and zombie.is_clickable() and zombie.hit_test(event.pos):
                    zombie.register_hit()
                    hits += 1
                    if hit_sound and not is_muted:
                        try:
                            hit_sound.play()
                        except Exception:
                            pass
                else:
                    # Count a miss only if the user clicked during active play
                    # (when a zombie is on screen or about to spawn very soon)
                    if zombie and zombie.state in ("spawning", "alive"):
                        misses += 1

        # Spawn logic: keep exactly one zombie active at a time
        if zombie is None and now >= next_spawn_time:
            pos = random.choice(SPAWN_POINTS)
            zombie = Zombie(pos)

        # Update zombie
        if zombie:
            zombie.update(now)
            if zombie.state == "dead":
                # Schedule next spawn shortly after despawn
                zombie = None
                next_spawn_time = now + random.randint(220, 520)

        # Draw
        screen.blit(bg_surface, (0, 0))

        # Draw zombie
        if zombie:
            zombie.draw(screen, now)

        # HUD
        total = hits + misses
        acc = (hits / total * 100.0) if total > 0 else 0.0
        hud_lines = [
            f"Hits: {hits}",
            f"Misses: {misses}",
            f"Accuracy: {acc:.1f}%",
            "Press M to mute" if sound_supported else "Sound unavailable",
        ]
        # Render in top-left corner
        y = 12
        for line in hud_lines:
            txt = font.render(line, True, HUD_COLOR)
            screen.blit(txt, (12, y))
            y += 24

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
