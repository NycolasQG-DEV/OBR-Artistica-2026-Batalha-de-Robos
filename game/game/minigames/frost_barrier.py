# game/minigames/frost_barrier.py
# ═══════════════════════════════════════════════════════════════════════
# Minigame "ESCUDO DE GELO / FROST BARRIER" — PenLinux
# ═══════════════════════════════════════════════════════════════════════
# O jogador acerta os núcleos de gelo energéticos que flutuam e rebatem
# nas bordas da tela e uns nos outros.
# ═══════════════════════════════════════════════════════════════════════

import random
import time
import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath
from game.minigames.base_minigame import BaseAttackMinigame
from game.config.battle import MINIGAME_DURATION

CORE_RADIUS_NORM = 0.080  # Tamanho aumentado dos núcleos de gelo
HIT_RADIUS_NORM = 0.11   # Raio de detecção por passagem/hover da mão

class FrostBarrierMinigame(BaseAttackMinigame):
    instruction_text = "❄️  ESCUDO DE GELO!\nAcerte os núcleos de gelo que rebatem\nna tela antes que o tempo acabe!"
    instruction_icon = "❄️"
    explanation_sound = "assets/sounds/penlinux/minigames/frost_barrier.wav"
    duration = 10.0  # seconds of active gameplay

    def on_start(self):
        self._cores = []         # List of bouncing ice cores: {id, x, y, vx, vy, radius, scale, rot, spin_speed}
        self._shattered = []     # List of shattering particles: {x, y, scale, alpha, particles}
        self._core_counter = 0
        self._hits = 0

        self._particles = []
        self._floating_texts = []
        self._shake_amount = 0.0
        self._screen_flash = 0.0
        self._snd_ice = None

        # Carrega o som de estilhaço de gelo na inicialização
        try:
            from engine import app_core as app
            if app.game_instance and hasattr(app.game_instance, "loader"):
                self._snd_ice = app.game_instance.loader.loadSfx("assets/sounds/ice_shatter.wav")
        except Exception:
            pass

        # Spawn initial 10 bouncing ice cores with random positions and velocities
        for _ in range(10):
            self._spawn_ice_core()

    def _play_ice_sound(self):
        if self._snd_ice:
            try:
                self._snd_ice.play()
            except Exception:
                pass

    def _spawn_ice_core(self):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(0.20, 0.32)  # normalized velocity per second
        self._cores.append({
            "id": self._core_counter,
            "x": random.uniform(0.20, 0.80),
            "y": random.uniform(0.25, 0.75),
            "vx": speed * math.cos(angle),
            "vy": speed * math.sin(angle),
            "radius": CORE_RADIUS_NORM,
            "scale": 0.0,  # smooth scale entry
            "rot": random.uniform(0, 360),
            "spin_speed": random.choice([-1, 1]) * random.uniform(50, 110)
        })
        self._core_counter += 1

    def on_update(self, hand_pos, hand_closed, dt):
        # Decay visual screen shaking and flash effects
        if self._shake_amount > 0:
            self._shake_amount = max(0.0, self._shake_amount - 50.0 * dt)
        if self._screen_flash > 0:
            self._screen_flash = max(0.0, self._screen_flash - dt * 2.0)

        # 1. Update active ice core movement & rotations
        num_cores = len(self._cores)
        for i, c in enumerate(self._cores):
            if c["scale"] < 1.0:
                c["scale"] = min(1.0, c["scale"] + 8.0 * dt)

            c["rot"] = (c["rot"] + c["spin_speed"] * dt) % 360.0

            # Move
            c["x"] += c["vx"] * dt
            c["y"] += c["vy"] * dt

            # Wall Bounce (Screen Boundaries)
            margin_x = 0.10
            margin_y = 0.15
            if c["x"] < margin_x:
                c["x"] = margin_x
                c["vx"] = abs(c["vx"])
            elif c["x"] > (1.0 - margin_x):
                c["x"] = 1.0 - margin_x
                c["vx"] = -abs(c["vx"])

            if c["y"] < margin_y:
                c["y"] = margin_y
                c["vy"] = abs(c["vy"])
            elif c["y"] > (1.0 - margin_y):
                c["y"] = 1.0 - margin_y
                c["vy"] = -abs(c["vy"])

        # Core-to-Core elastic collisions
        for i in range(num_cores):
            for j in range(i + 1, num_cores):
                c1 = self._cores[i]
                c2 = self._cores[j]
                dx = c2["x"] - c1["x"]
                dy = c2["y"] - c1["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                min_dist = c1["radius"] + c2["radius"]

                if dist < min_dist and dist > 0.0001:
                    # Normal vector
                    nx = dx / dist
                    ny = dy / dist
                    # Separate overlap
                    overlap = 0.5 * (min_dist - dist)
                    c1["x"] -= nx * overlap
                    c1["y"] -= ny * overlap
                    c2["x"] += nx * overlap
                    c2["y"] += ny * overlap

                    # Relative velocity along normal
                    kx = c1["vx"] - c2["vx"]
                    ky = c1["vy"] - c2["vy"]
                    p = 2.0 * (nx * kx + ny * ky) / 2.0

                    # Bounce velocities
                    c1["vx"] -= p * nx
                    c1["vy"] -= p * ny
                    c2["vx"] += p * nx
                    c2["vy"] += p * ny

        # 2. Update shattered ice particles
        for s in self._shattered:
            s["alpha"] = max(0.0, s["alpha"] - dt * 2.5)
            for p in s["particles"]:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["rot"] += p["spin"] * dt
        self._shattered = [s for s in self._shattered if s["alpha"] > 0]

        # 3. Coleta INSTANTÂNEA ao passar a mão em cima (Hover touch targeting)
        positions_to_check = []
        if hand_pos and hand_pos[0] is not None and hand_pos[1] is not None:
            positions_to_check.append(hand_pos)

        from engine import app_core as app
        if app.game_instance:
            # Obtém todas as mãos detectadas pelo CV (multi-hand tracking)
            if hasattr(app.game_instance, "cv_input") and app.game_instance.cv_input:
                hands = app.game_instance.cv_input.get_hands_landmarks()
                for hand in hands:
                    if "pos" in hand and hand["pos"]:
                        positions_to_check.append(hand["pos"])
            
            # Fallback para o mouse ou dedo único se CV falhar/não tiver múltiplas mãos
            if hasattr(app.game_instance, "_finger_pos_norm"):
                cpos = app.game_instance._finger_pos_norm
                if cpos and cpos[0] is not None and cpos[1] is not None:
                    positions_to_check.append(cpos)

        targets_to_remove = set()
        for pos in positions_to_check:
            px, py = pos[0], pos[1]
            for c in self._cores:
                dist = math.sqrt((c["x"] - px)**2 + (c["y"] - py)**2)
                if dist <= HIT_RADIUS_NORM:
                    targets_to_remove.add(c["id"])

        if targets_to_remove:
            self._hits += len(targets_to_remove)
            self._play_ice_sound()
            for c in self._cores:
                if c["id"] in targets_to_remove:
                    self._create_shatter_effect(c["x"], c["y"])

            # Remove núcleos coletados e gera novos INSTANTANEAMENTE
            self._cores = [c for c in self._cores if c["id"] not in targets_to_remove]
            self._shake_amount = 14.0
            self._screen_flash = 0.35

            while len(self._cores) < 10:
                self._spawn_ice_core()

    def _create_shatter_effect(self, x, y):
        shards = []
        for _ in range(10):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(0.15, 0.45)
            shards.append({
                "x": x,
                "y": y,
                "vx": spd * math.cos(ang),
                "vy": spd * math.sin(ang),
                "size": random.uniform(8, 16),
                "rot": random.uniform(0, 360),
                "spin": random.uniform(-180, 180)
            })
        self._shattered.append({
            "x": x,
            "y": y,
            "alpha": 1.0,
            "particles": shards
        })

    def evaluate(self) -> str:
        if self._hits >= 20:
            return "excellent"
        elif self._hits >= 10:
            return "good"
        else:
            return "poor"

    def paint(self, painter, width: int, height: int, scale: float):
        self.draw(painter, width, height)

    def draw(self, painter, width, height):
        painter.save()

        # Draw pulsing screen vignette/flash effect
        if self._screen_flash > 0:
            flash_color = QColor(0, 220, 255, int(self._screen_flash * 100))
            painter.fillRect(0, 0, width, height, flash_color)

        # Draw shattered ice shards
        for s in self._shattered:
            alpha_byte = int(s["alpha"] * 255)
            pen = QPen(QColor(180, 240, 255, alpha_byte), 2)
            brush = QBrush(QColor(100, 200, 255, int(s["alpha"] * 180)))
            painter.setPen(pen)
            painter.setBrush(brush)

            for p in s["particles"]:
                px = p["x"] * width
                py = p["y"] * height
                sz = p["size"]
                painter.save()
                painter.translate(px, py)
                painter.rotate(p["rot"])
                rect = QRectF(-sz / 2, -sz / 2, sz, sz)
                painter.drawRect(rect)
                painter.restore()

        # Draw bouncing ice cores
        for c in self._cores:
            cx = c["x"] * width
            cy = c["y"] * height
            r = c["radius"] * width * c["scale"]

            painter.save()
            painter.translate(cx, cy)
            painter.rotate(c["rot"])

            # Outer cyan ice glow
            glow = QRadialGradient(0, 0, r * 1.5)
            glow.setColorAt(0.0, QColor(0, 230, 255, 200))
            glow.setColorAt(0.5, QColor(0, 160, 255, 100))
            glow.setColorAt(1.0, QColor(0, 100, 255, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(0, 0), r * 1.5, r * 1.5)

            # Diamond crystal ice core shape
            path = QPainterPath()
            path.moveTo(0, -r)
            path.lineTo(r * 0.85, 0)
            path.lineTo(0, r)
            path.lineTo(-r * 0.85, 0)
            path.closeSubpath()

            grad = QLinearGradient(-r, -r, r, r)
            grad.setColorAt(0.0, QColor(220, 255, 255, 240))
            grad.setColorAt(0.5, QColor(50, 180, 255, 220))
            grad.setColorAt(1.0, QColor(0, 90, 220, 240))

            pen = QPen(QColor(255, 255, 255, 240), 2.5)
            painter.setPen(pen)
            painter.setBrush(QBrush(grad))
            painter.drawPath(path)

            # Inner crystal detail lines
            detail_pen = QPen(QColor(255, 255, 255, 180), 1.5)
            painter.setPen(detail_pen)
            painter.drawLine(QPointF(0, -r * 0.6), QPointF(0, r * 0.6))
            painter.drawLine(QPointF(-r * 0.5, 0), QPointF(r * 0.5, 0))

            painter.restore()


# ═══════════════════════════════════════════════════════════════════════
# Animação de ataque 3D para Escudo de Gelo (Frost Barrier)
# ═══════════════════════════════════════════════════════════════════════

async def execute_frost_barrier_attack(robot, target, ability, final_damage, camera, ctx):
    from game.champions.robot_base import PL_ATTACK, PL_MOV, DB_MOV, WAIT_MOV, DELAY
    from game.combat.battle_logic import wait_seconds

    rating = ctx.mini_game_result
    if isinstance(ctx.mini_game_result, dict):
        rating = ctx.mini_game_result.get("rating", "good")

    if final_damage == 0:
        ctx.create_floating(robot.v_tx, robot.v_ty, "MISSED!", (1.0, 0.2, 0.2, 1.0), size=1.1)
    else:
        if rating == "excellent":
            ctx.create_floating(robot.v_tx, robot.v_ty, "FROST MASTER!", (0.0, 1.0, 0.8, 1.0), size=1.5)
        elif rating == "good":
            ctx.create_floating(robot.v_tx, robot.v_ty, "ICE SHIELD!", (0.0, 0.9, 1.0, 1.0), size=1.3)
        else:
            ctx.create_floating(robot.v_tx, robot.v_ty, "WEAK BARRIER", (1.0, 0.5, 0.2, 1.0), size=1.1)

    # 1. Posiciona a câmera na lateral (estilo Meteor Stomp do DinoByte)
    if camera:
        if hasattr(camera, "enter_meteor_stomp_mode"):
            camera.enter_meteor_stomp_mode(robot)
        else:
            camera._mode = camera.MODE_MINIGAME
            camera._target_heading = 90.0

    # 2. Animação de carregamento do escudo -> NO MOMENTO DA EXPLOSÃO: DANO + CAMERASHAKE DE 2s!
    from engine import app_core as app
    if app.game_instance and hasattr(app.game_instance, "_trigger_3d_barrier_explosion"):
        async def on_explode():
            from settings import SHAKE_HEAVY
            if camera and hasattr(camera, "shake"):
                camera.shake(SHAKE_HEAVY, duration=2.0)
            elif camera and hasattr(camera, "add_shake"):
                camera.add_shake(SHAKE_HEAVY)
            if final_damage > 0:
                await PL_ATTACK(ctx, final_damage)
                await WAIT_MOV()

        await app.game_instance._trigger_3d_barrier_explosion(on_explode_callback=on_explode)

    # 3. Retorna a câmera para a visão normal de combate
    if camera:
        camera.enter_battle_mode()

    # 4. Ambos os robôs (PenLinux e DinoByte) recuam 1 tile para trás
    await PL_MOV(ctx, "TRAS", 1)
    await DB_MOV(ctx, "TRAS", 1)
    await WAIT_MOV()

    return True
