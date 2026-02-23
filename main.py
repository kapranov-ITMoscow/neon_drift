import json
import math
import os
import random
from dataclasses import dataclass

import pygame
from pygame.math import Vector2

# ==============================
# Настройки игры
# ==============================
WIDTH, HEIGHT = 960, 600
FPS = 60
TITLE = "Neon Drift Arena"

DATA_FILE = "save_data.json"

# Цвета (RGB)
BG = (10, 12, 18)
PANEL = (18, 22, 32)
WHITE = (235, 240, 255)
MUTED = (150, 160, 190)
RED = (255, 90, 120)
GREEN = (80, 255, 170)
BLUE = (80, 180, 255)
YELLOW = (255, 215, 90)
PURPLE = (180, 110, 255)


def clamp(value, a, b):
    return max(a, min(b, value))


def load_best_score():
    """Загружает лучший результат из json-файла."""
    if not os.path.exists(DATA_FILE):
        return 0
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("best_score", 0))
    except Exception:
        return 0


def save_best_score(score):
    """Сохраняет лучший результат в json-файл."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"best_score": int(score)}, f, ensure_ascii=False, indent=2)
    except Exception:
        # Не падаем из-за проблем записи
        pass


class Timer:
    """Простой таймер обратного отсчета в секундах."""
    def __init__(self):
        self.time_left = 0.0

    def start(self, seconds: float):
        self.time_left = max(0.0, float(seconds))

    def update(self, dt: float):
        self.time_left = max(0.0, self.time_left - dt)

    @property
    def active(self) -> bool:
        return self.time_left > 0.0


@dataclass
class Particle:
    pos: Vector2
    vel: Vector2
    life: float
    max_life: float
    radius: float
    color: tuple

    def update(self, dt: float):
        self.pos += self.vel * dt
        self.vel *= 0.97
        self.life -= dt

    def draw(self, surface: pygame.Surface):
        if self.life <= 0:
            return
        alpha = clamp(self.life / self.max_life, 0.0, 1.0)
        r = max(1, int(self.radius * (0.6 + alpha)))
        tmp = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(
            tmp,
            (*self.color, int(170 * alpha)),
            (tmp.get_width() // 2, tmp.get_height() // 2),
            r,
        )
        surface.blit(tmp, (self.pos.x - tmp.get_width() / 2, self.pos.y - tmp.get_height() / 2))


class Player:
    """Игрок: перемещение, рывок (dash), столкновение."""
    def __init__(self):
        self.pos = Vector2(WIDTH / 2, HEIGHT / 2)
        self.vel = Vector2()
        self.radius = 16
        self.base_speed = 280
        self.alive = True

        self.dash_timer = Timer()
        self.dash_cooldown = Timer()
        self.invuln_timer = Timer()

        self.dash_direction = Vector2(1, 0)
        self.trail_accum = 0.0

    def handle_input(self, dt: float):
        keys = pygame.key.get_pressed()

        # Вектор направления от клавиш WASD / стрелок
        direction = Vector2(
            (1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0)
            - (1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0),
            (1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0)
            - (1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0),
        )

        if direction.length_squared() > 0:
            direction = direction.normalize()
            self.dash_direction = direction
        else:
            direction = Vector2()

        # Если рывок активен — обычное движение отключаем
        if self.dash_timer.active:
            self.vel = self.dash_direction * 780
        else:
            target_vel = direction * self.base_speed
            # Плавность управления (инерция)
            self.vel = self.vel.lerp(target_vel, clamp(dt * 10.0, 0.0, 1.0))

        # Рывок по Space / Shift
        dash_pressed = keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        if dash_pressed and (not self.dash_timer.active) and (not self.dash_cooldown.active):
            if self.dash_direction.length_squared() == 0:
                self.dash_direction = Vector2(1, 0)
            self.dash_timer.start(0.12)
            self.dash_cooldown.start(1.0)
            self.invuln_timer.start(0.18)

    def update(self, dt: float):
        self.dash_timer.update(dt)
        self.dash_cooldown.update(dt)
        self.invuln_timer.update(dt)

        self.pos += self.vel * dt

        # Ограничение игрока внутри окна
        self.pos.x = clamp(self.pos.x, self.radius, WIDTH - self.radius)
        self.pos.y = clamp(self.pos.y, self.radius, HEIGHT - self.radius)

    def can_be_hit(self):
        return not self.invuln_timer.active

    def draw(self, surface: pygame.Surface):
        # Внешнее свечение
        glow_r = self.radius + 10
        glow = pygame.Surface((glow_r * 2 + 8, glow_r * 2 + 8), pygame.SRCALPHA)
        pulse = 0.8 + 0.2 * math.sin(pygame.time.get_ticks() * 0.01)
        glow_alpha = 90 if not self.invuln_timer.active else 150
        pygame.draw.circle(
            glow,
            (80, 200, 255, int(glow_alpha * pulse)),
            (glow.get_width() // 2, glow.get_height() // 2),
            glow_r,
        )
        surface.blit(glow, (self.pos.x - glow.get_width() / 2, self.pos.y - glow.get_height() / 2))

        # Тело игрока
        body_color = BLUE if not self.invuln_timer.active else YELLOW
        pygame.draw.circle(surface, body_color, (int(self.pos.x), int(self.pos.y)), self.radius)
        pygame.draw.circle(surface, WHITE, (int(self.pos.x), int(self.pos.y)), self.radius - 6)

        # Небольшая "стрелка" направления
        nose = self.pos + self.dash_direction * (self.radius + 6)
        pygame.draw.line(surface, body_color, self.pos, nose, 3)


class Enemy:
    """Враг — движется по направлению и отскакивает от границ."""
    def __init__(self, difficulty_level: int):
        spawn_side = random.choice(["top", "bottom", "left", "right"])

        margin = 30
        if spawn_side == "top":
            self.pos = Vector2(random.randint(0, WIDTH), -margin)
            direction = Vector2(random.uniform(-0.6, 0.6), random.uniform(0.4, 1.0))
        elif spawn_side == "bottom":
            self.pos = Vector2(random.randint(0, WIDTH), HEIGHT + margin)
            direction = Vector2(random.uniform(-0.6, 0.6), random.uniform(-1.0, -0.4))
        elif spawn_side == "left":
            self.pos = Vector2(-margin, random.randint(0, HEIGHT))
            direction = Vector2(random.uniform(0.4, 1.0), random.uniform(-0.6, 0.6))
        else:
            self.pos = Vector2(WIDTH + margin, random.randint(0, HEIGHT))
            direction = Vector2(random.uniform(-1.0, -0.4), random.uniform(-0.6, 0.6))

        self.direction = direction.normalize()
        self.radius = random.randint(10, 22)

        # Скорость растёт от сложности
        base_speed = random.uniform(140, 220)
        self.speed = base_speed + difficulty_level * random.uniform(4, 9)

        self.spin = random.uniform(-4, 4)
        self.angle = random.uniform(0, math.tau)
        self.color = random.choice([RED, PURPLE, (255, 120, 80)])

    def update(self, dt: float):
        self.pos += self.direction * self.speed * dt
        self.angle += self.spin * dt

        # Мягкий отскок от границ внутри экрана
        if self.pos.x < self.radius:
            self.pos.x = self.radius
            self.direction.x *= -1
        elif self.pos.x > WIDTH - self.radius:
            self.pos.x = WIDTH - self.radius
            self.direction.x *= -1

        if self.pos.y < self.radius:
            self.pos.y = self.radius
            self.direction.y *= -1
        elif self.pos.y > HEIGHT - self.radius:
            self.pos.y = HEIGHT - self.radius
            self.direction.y *= -1

    def draw(self, surface: pygame.Surface):
        # Свечение
        g = self.radius + 8
        glow = pygame.Surface((g * 2 + 6, g * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*self.color, 80), (glow.get_width() // 2, glow.get_height() // 2), g)
        surface.blit(glow, (self.pos.x - glow.get_width() / 2, self.pos.y - glow.get_height() / 2))

        # Тело
        pygame.draw.circle(surface, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)
        pygame.draw.circle(surface, (35, 35, 45), (int(self.pos.x), int(self.pos.y)), max(2, self.radius - 5))

        # "Лопасти" для движения
        for i in range(3):
            ang = self.angle + i * (math.tau / 3)
            p1 = self.pos + Vector2(math.cos(ang), math.sin(ang)) * (self.radius - 2)
            p2 = self.pos + Vector2(math.cos(ang + 0.35), math.sin(ang + 0.35)) * 6
            pygame.draw.line(surface, WHITE, p1, p2, 2)

    def collides_with_player(self, player: "Player") -> bool:
        dist2 = (self.pos - player.pos).length_squared()
        r = self.radius + player.radius
        return dist2 <= r * r


class EnergyOrb:
    """Сфера энергии: даёт очки и поддерживает комбо."""
    def __init__(self):
        margin = 40
        self.pos = Vector2(
            random.randint(margin, WIDTH - margin),
            random.randint(margin, HEIGHT - margin),
        )
        self.radius = 10
        self.pulse_phase = random.uniform(0, math.tau)
        self.value = 25

    def update(self, dt: float):
        self.pulse_phase += dt * 4.2

    def draw(self, surface: pygame.Surface):
        pulse = 1.0 + 0.15 * math.sin(self.pulse_phase)
        r = int(self.radius * pulse)

        glow_r = r + 10
        glow = pygame.Surface((glow_r * 2 + 8, glow_r * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(glow, (80, 255, 170, 90), (glow.get_width() // 2, glow.get_height() // 2), glow_r)
        surface.blit(glow, (self.pos.x - glow.get_width() / 2, self.pos.y - glow.get_height() / 2))

        pygame.draw.circle(surface, GREEN, (int(self.pos.x), int(self.pos.y)), r)
        pygame.draw.circle(surface, WHITE, (int(self.pos.x), int(self.pos.y)), max(2, r - 5))

    def collides_with_player(self, player: "Player") -> bool:
        dist2 = (self.pos - player.pos).length_squared()
        r = self.radius + player.radius
        return dist2 <= r * r


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        # Шрифты (системные)
        self.font_small = pygame.font.SysFont("consolas", 20)
        self.font_ui = pygame.font.SysFont("consolas", 26, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 56, bold=True)

        self.best_score = load_best_score()

        self.state = "menu"  # menu | playing | paused | gameover
        self.reset_run()

        # Эффект дрожания камеры
        self.shake_time = 0.0
        self.shake_strength = 0.0

        # Фоновые линии
        self.grid_offset = 0.0

    def reset_run(self):
        self.player = Player()
        self.enemies = []
        self.orbs = []
        self.particles = []

        self.score = 0
        self.time_alive = 0.0
        self.combo = 0
        self.combo_timer = Timer()

        self.spawn_enemy_timer = Timer()
        self.spawn_orb_timer = Timer()
        self.spawn_enemy_timer.start(0.6)
        self.spawn_orb_timer.start(2.2)

        self.difficulty_level = 1
        self.next_difficulty_time = 10.0

        # Начальные враги
        for _ in range(3):
            self.enemies.append(Enemy(self.difficulty_level))

    def add_shake(self, strength: float, duration: float = 0.18):
        self.shake_strength = max(self.shake_strength, strength)
        self.shake_time = max(self.shake_time, duration)

    def spawn_burst(self, pos: Vector2, color: tuple, count=16, speed=180):
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            vel = Vector2(math.cos(ang), math.sin(ang)) * random.uniform(speed * 0.4, speed)
            life = random.uniform(0.25, 0.55)
            self.particles.append(
                Particle(
                    pos=Vector2(pos.x, pos.y),
                    vel=vel,
                    life=life,
                    max_life=life,
                    radius=random.uniform(2, 4),
                    color=color,
                )
            )

    def update_playing(self, dt: float):
        self.time_alive += dt
        self.grid_offset += 18 * dt

        # Сложность каждые 10 секунд
        if self.time_alive >= self.next_difficulty_time:
            self.difficulty_level += 1
            self.next_difficulty_time += 10.0
            self.score += 20  # бонус за выживание на новом уровне
            self.spawn_burst(self.player.pos, YELLOW, count=10, speed=120)

        self.combo_timer.update(dt)
        if not self.combo_timer.active:
            self.combo = 0

        self.player.handle_input(dt)
        self.player.update(dt)

        self.spawn_enemy_timer.update(dt)
        self.spawn_orb_timer.update(dt)

        # Чем сложнее, тем чаще спавн врагов
        if not self.spawn_enemy_timer.active:
            self.enemies.append(Enemy(self.difficulty_level))
            next_time = max(
                0.28, 1.0 - self.difficulty_level * 0.045 + random.uniform(-0.08, 0.12)
            )
            self.spawn_enemy_timer.start(next_time)

        # Сферы энергии (не больше 3 одновременно)
        if (not self.spawn_orb_timer.active) and len(self.orbs) < 3:
            self.orbs.append(EnergyOrb())
            self.spawn_orb_timer.start(random.uniform(2.0, 3.4))

        for enemy in self.enemies:
            enemy.update(dt)

        for orb in self.orbs:
            orb.update(dt)

        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]

        # Следы от быстрого движения
        speed_len = self.player.vel.length()
        if speed_len > 250:
            self.player.trail_accum += dt
            while self.player.trail_accum >= 0.018:
                self.player.trail_accum -= 0.018
                backward = self.player.vel.normalize() if speed_len > 0 else Vector2()
                pos = self.player.pos - backward * random.uniform(4, 16)
                vel = Vector2(random.uniform(-20, 20), random.uniform(-20, 20))
                self.particles.append(Particle(Vector2(pos), vel, 0.2, 0.2, 3, BLUE))

        # Подбор сферы энергии
        picked = []
        for orb in self.orbs:
            if orb.collides_with_player(self.player):
                picked.append(orb)
                self.combo += 1
                self.combo_timer.start(2.0)

                combo_bonus = (self.combo - 1) * 5
                self.score += orb.value + combo_bonus
                self.spawn_burst(orb.pos, GREEN, count=14, speed=150)
                self.add_shake(4, 0.08)

        if picked:
            self.orbs = [o for o in self.orbs if o not in picked]

        # Пассивные очки за выживание
        self.score += int(dt * 6)

        # Столкновения с врагами
        for enemy in self.enemies:
            if enemy.collides_with_player(self.player):
                if self.player.can_be_hit():
                    self.player.alive = False
                    self.spawn_burst(self.player.pos, RED, count=32, speed=260)
                    self.add_shake(10, 0.25)
                    self.state = "gameover"
                    self.best_score = max(self.best_score, self.score)
                    save_best_score(self.best_score)
                    break
                else:
                    # Во время неуязвимости от рывка — отталкиваем врага и даём чуть очков
                    push = enemy.pos - self.player.pos
                    if push.length_squared() > 0:
                        enemy.direction = push.normalize()
                    enemy.speed *= 0.92
                    self.score += 2

        # Ограничим число врагов, чтобы не было перегруза
        if len(self.enemies) > 70:
            self.enemies = self.enemies[-70:]

        # Обновление эффекта дрожания
        if self.shake_time > 0:
            self.shake_time = max(0.0, self.shake_time - dt)
            if self.shake_time == 0:
                self.shake_strength = 0.0

    def draw_background(self, target_surface: pygame.Surface):
        target_surface.fill(BG)

        # Сетка с лёгкой анимацией
        spacing = 40
        ox = int(self.grid_offset) % spacing
        oy = int(self.grid_offset * 0.6) % spacing

        grid_color = (24, 28, 40)
        for x in range(-spacing, WIDTH + spacing, spacing):
            pygame.draw.line(target_surface, grid_color, (x + ox, 0), (x + ox, HEIGHT), 1)
        for y in range(-spacing, HEIGHT + spacing, spacing):
            pygame.draw.line(target_surface, grid_color, (0, y + oy), (WIDTH, y + oy), 1)

        # Декоративные диагонали
        for i in range(0, WIDTH, 120):
            pygame.draw.line(target_surface, (18, 22, 35), (i, 0), (i - 180, HEIGHT), 1)

    def draw_ui(self, target_surface: pygame.Surface):
        panel_rect = pygame.Rect(12, 12, WIDTH - 24, 78)
        pygame.draw.rect(target_surface, PANEL, panel_rect, border_radius=14)
        pygame.draw.rect(target_surface, (35, 45, 65), panel_rect, 2, border_radius=14)

        score_text = self.font_ui.render(f"SCORE: {self.score}", True, WHITE)
        best_text = self.font_small.render(f"BEST: {self.best_score}", True, MUTED)
        time_text = self.font_small.render(f"TIME: {self.time_alive:05.1f}s", True, MUTED)

        target_surface.blit(score_text, (26, 22))
        target_surface.blit(best_text, (28, 55))
        target_surface.blit(time_text, (180, 55))

        lvl_text = self.font_ui.render(f"LVL {self.difficulty_level}", True, YELLOW)
        target_surface.blit(lvl_text, (WIDTH - 190, 22))

        hint = self.font_small.render(
            "WASD/Arrows - move | SPACE/SHIFT - dash | P - pause",
            True,
            MUTED,
        )
        target_surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, 55))

        if self.combo > 1 and self.combo_timer.active:
            combo_txt = self.font_ui.render(f"COMBO x{self.combo}", True, GREEN)
            target_surface.blit(combo_txt, (WIDTH // 2 - combo_txt.get_width() // 2, 102))

        # Полоса кулдауна рывка
        x, y, w, h = 26, 102, 220, 14
        pygame.draw.rect(target_surface, (22, 26, 36), (x, y, w, h), border_radius=7)
        pygame.draw.rect(target_surface, (40, 48, 66), (x, y, w, h), 1, border_radius=7)

        ready_ratio = 1.0
        if self.player.dash_cooldown.active:
            ready_ratio = clamp(1.0 - self.player.dash_cooldown.time_left / 1.0, 0.0, 1.0)

        fill_w = int((w - 2) * ready_ratio)
        if fill_w > 0:
            pygame.draw.rect(target_surface, BLUE, (x + 1, y + 1, fill_w, h - 2), border_radius=7)

        dash_label = self.font_small.render("Dash", True, MUTED)
        target_surface.blit(dash_label, (x, y + 18))

    def draw_world(self, target_surface: pygame.Surface):
        self.draw_background(target_surface)

        for orb in self.orbs:
            orb.draw(target_surface)

        for enemy in self.enemies:
            enemy.draw(target_surface)

        for p in self.particles:
            p.draw(target_surface)

        self.player.draw(target_surface)
        self.draw_ui(target_surface)

    def draw_center_panel(self, title: str, lines: list[str], accent=BLUE):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 620, 320
        rect = pygame.Rect(
            WIDTH // 2 - panel_w // 2,
            HEIGHT // 2 - panel_h // 2,
            panel_w,
            panel_h,
        )
        pygame.draw.rect(self.screen, (14, 18, 28), rect, border_radius=18)
        pygame.draw.rect(self.screen, (34, 46, 70), rect, 2, border_radius=18)
        pygame.draw.rect(self.screen, accent, (rect.x, rect.y, rect.w, 6), border_radius=18)

        title_surf = self.font_big.render(title, True, WHITE)
        self.screen.blit(title_surf, (rect.centerx - title_surf.get_width() // 2, rect.y + 24))

        y = rect.y + 118
        for line in lines:
            surf = self.font_ui.render(line, True, MUTED if not line.startswith(">") else WHITE)
            self.screen.blit(surf, (rect.centerx - surf.get_width() // 2, y))
            y += 40

    def draw(self):
        world = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.draw_world(world)

        # Смещение камеры (дрожание)
        if self.shake_time > 0 and self.shake_strength > 0:
            ox = random.randint(-int(self.shake_strength), int(self.shake_strength))
            oy = random.randint(-int(self.shake_strength), int(self.shake_strength))
        else:
            ox = oy = 0

        self.screen.fill(BG)
        self.screen.blit(world, (ox, oy))

        if self.state == "menu":
            self.draw_center_panel(
                "NEON DRIFT ARENA",
                [
                    "Уклоняйся от дронов и собирай сферы энергии",
                    "Рывок даёт короткую неуязвимость",
                    "> ENTER - начать игру",
                    "> ESC - выход",
                ],
                accent=BLUE,
            )
        elif self.state == "paused":
            self.draw_center_panel(
                "PAUSE",
                [
                    "Игра поставлена на паузу",
                    "> P / ENTER - продолжить",
                    "> R - начать заново",
                    "> ESC - в меню",
                ],
                accent=YELLOW,
            )
        elif self.state == "gameover":
            self.draw_center_panel(
                "GAME OVER",
                [
                    f"Счёт: {self.score}",
                    f"Лучший результат: {self.best_score}",
                    "> ENTER - ещё раз",
                    "> ESC - в меню",
                ],
                accent=RED,
            )

        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if self.state == "menu":
                    if event.key == pygame.K_RETURN:
                        self.reset_run()
                        self.state = "playing"
                    elif event.key == pygame.K_ESCAPE:
                        return False

                elif self.state == "playing":
                    if event.key == pygame.K_p:
                        self.state = "paused"
                    elif event.key == pygame.K_r:
                        self.reset_run()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "menu"

                elif self.state == "paused":
                    if event.key in (pygame.K_p, pygame.K_RETURN):
                        self.state = "playing"
                    elif event.key == pygame.K_r:
                        self.reset_run()
                        self.state = "playing"
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "menu"

                elif self.state == "gameover":
                    if event.key == pygame.K_RETURN:
                        self.reset_run()
                        self.state = "playing"
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "menu"

        return True

    def run(self):
        running = True
        while running:
            dt_ms = self.clock.tick(FPS)
            dt = clamp(dt_ms / 1000.0, 0.0, 0.05)

            running = self.handle_events()

            if self.state == "playing":
                self.update_playing(dt)

            self.draw()

        pygame.quit()


if __name__ == "__main__":
    Game().run()
