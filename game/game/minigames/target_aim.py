# combat/minigames/target_aim/target_aim_minigame.py
# ═══════════════════════════════════════════════════════════════════════
# Minigame "MORDIDA JURÁSSICA" — Devore presas em cadeia com visão computacional
# ═══════════════════════════════════════════════════════════════════════
# O jogador controla bocas cibernéticas de dinossauro com as duas mãos.
# Quando a mão se fecha, as mandíbulas se fecham rápido (mordida).
# O objetivo é alinhar as bocas sobre as presas (pedaços de carne) que surgem
# em cadeia espalhadas pela tela e morder para devorá-las no tempo limite.
# Resultado:
#   12+ = excellent, 6-11 = good, 0-5 = poor
# ═══════════════════════════════════════════════════════════════════════

import random
import time
import math
from game.minigames.base_minigame import BaseAttackMinigame
from game.config.battle import MINIGAME_DURATION

TARGET_RADIUS_NORM = 0.11   # Radius in normalized coords (larger for better gameplay)
HIT_RADIUS_NORM = 0.15      # Biting hit radius (larger for satisfying chomps)


class JurassicBiteMinigame(BaseAttackMinigame):
    instruction_text = "🦖  MORDIDA JURÁSSICA!\nAlinhe as duas mãos para morder as presas!"
    instruction_icon = "🦖"
    explanation_sound = "assets/sounds/dinobyte/minigames/jurassic_bite.wav"
    duration = 10.0  # seconds of active gameplay

    def on_start(self):
        self._targets = []       # List of active targets: dicts with {id, x, y, scale}
        self._dead_targets = []  # List of hit targets playing fadeout: {x, y, scale, flash_hit}
        self._target_counter = 0 # To assign unique ids
        self._hits = 0
        
        # Track states for up to 2 hands dynamically
        self._prev_closed = [False, False]
        self._jaw_gaps = [40.0, 40.0]
        
        # Local effects
        self._particles = []
        self._floating_texts = []
        self._hitstop_timer = 0.0
        self._shake_amount = 0.0
        self._screen_flash = 0.0

        # Cache de hands copiado em on_update() para evitar lock dentro do paintEvent
        self._cached_hands = []
        self._cached_input_mode = "cv"

        # Garante que o robô físico permaneça imóvel no chão durante o minigame de mira
        from game.combat.serial_controller import get_serial_controller
        get_serial_controller().send_command_realtime("DinoByte", "STOP", 0)

        # Pre-load temporary bite sounds
        self._bite_sounds = []
        from engine import app_core as app
        if app.game_instance and hasattr(app.game_instance, "loader"):
            for i in range(1, 4):
                try:
                    snd = app.game_instance.loader.loadSfx(f"assets/sounds/dinobyte/byte{i}.wav")
                    if snd:
                        snd.setVolume(1.0)
                        self._bite_sounds.append(snd)
                except Exception as e:
                    print(f"[JurassicBite] Erro ao carregar som de mordida {i}: {e}")


        # Spawn initial 4 targets in a chain
        px = random.uniform(0.35, 0.65)
        py = random.uniform(0.40, 0.60)
        
        # Head of the chain
        self._add_new_target(px, py)
        
        # Subsequent targets in the chain
        for _ in range(3):
            nx, ny = self._generate_next_position(px, py)
            self._add_new_target(nx, ny)
            px, py = nx, ny

    def _add_new_target(self, x, y):
        self._targets.append({
            "id": self._target_counter,
            "x": x,
            "y": y,
            "scale": 0.0,
            "spawn_time": time.time()
        })
        self._target_counter += 1

    def _generate_next_position(self, px, py):
        for _ in range(50):
            angle = random.uniform(0, math.tau)
            # Increased distance between consecutive targets to spread them more
            dist = random.uniform(0.24, 0.36)
            nx = px + dist * math.cos(angle)
            ny = py + dist * math.sin(angle)
            
            # Widen bounds to spread across the screen
            if 0.10 <= nx <= 0.90 and 0.15 <= ny <= 0.85:
                # Ensure it's not too close to the second-to-last target to avoid sharp doubling back
                if len(self._targets) < 2 or math.sqrt((nx - self._targets[-2]["x"])**2 + (ny - self._targets[-2]["y"])**2) > 0.20:
                    return nx, ny
        
        # Fallback to wider screen bounds
        return random.uniform(0.15, 0.85), random.uniform(0.20, 0.80)

    def on_update(self, hand_pos, hand_closed, dt):
        # 1. Hitstop (frame freeze effect on hit)
        if self._hitstop_timer > 0:
            self._hitstop_timer -= dt
            return

        # Decay visual screen-shaking and flash effects
        if self._shake_amount > 0:
            self._shake_amount = max(0.0, self._shake_amount - 55.0 * dt)
        if self._screen_flash > 0:
            self._screen_flash = max(0.0, self._screen_flash - dt)

        # Update scales for active targets (smooth scale-in entry animation)
        for t in self._targets:
            if t["scale"] < 1.0:
                t["scale"] = min(1.0, t["scale"] + 6.0 * dt)

        # Update dead targets fade-out animations
        for dtg in self._dead_targets:
            dtg["flash_hit"] = max(0.0, dtg["flash_hit"] - dt)
        self._dead_targets = [dtg for dtg in self._dead_targets if dtg["flash_hit"] > 0]

        # ── Coleta hands e armazena em cache (FORA do paintEvent, sem lock no paint) ──
        from engine import app_core as app
        input_mode = "cv"
        if app.game_instance and hasattr(app.game_instance, "_input_mode"):
            input_mode = app.game_instance._input_mode
        self._cached_input_mode = input_mode

        hands_list = []
        if input_mode == "cv" and app.game_instance and app.game_instance.cv_input:
            with app.game_instance.cv_input._lock:
                hands_list = list(app.game_instance.cv_input.detected_hands)
        
        # Fallback to mouse or single hand if cv_input is empty or in mouse mode
        if not hands_list:
            if hand_pos is not None:
                hands_list = [{"pos": hand_pos, "closed": hand_closed}]

        # Atualiza o cache que o paint() usará sem precisar de lock
        self._cached_hands = hands_list

        # Check hits for each hand individually
        for h_idx, hand in enumerate(hands_list):
            h_pos = hand["pos"]
            h_closed = hand["closed"]

            # Pad state lists if new hand index appears
            while len(self._prev_closed) <= h_idx:
                self._prev_closed.append(False)
            while len(self._jaw_gaps) <= h_idx:
                self._jaw_gaps.append(40.0)

            # Detect chomp trigger for this hand
            chomp_triggered = h_closed and not self._prev_closed[h_idx]
            self._prev_closed[h_idx] = h_closed

            # Smooth jaw animation gap for this hand
            target_gap = 0.0 if h_closed else 40.0
            self._jaw_gaps[h_idx] += (target_gap - self._jaw_gaps[h_idx]) * min(1.0, 22.0 * dt)

            # Play fast whoosh sound when player bites (sound juice!)
            if chomp_triggered:
                if app.game_instance and hasattr(app.game_instance, "snd_dodge") and app.game_instance.snd_dodge:
                    app.game_instance.snd_dodge.play()

            # Check target collisions for this hand
            if h_pos is not None and chomp_triggered:

                hx, hy = h_pos
                hit_index = -1
                
                # Find closest active target within range
                closest_dist = float('inf')
                for i, target in enumerate(self._targets):
                    dist = math.sqrt((hx - target["x"])**2 + (hy - target["y"])**2)
                    if dist <= HIT_RADIUS_NORM and dist < closest_dist:
                        closest_dist = dist
                        hit_index = i
                
                if hit_index != -1:
                    # We have a hit!
                    hit_target = self._targets.pop(hit_index)
                    
                    # Move to dead targets for hit animation
                    self._dead_targets.append({
                        "x": hit_target["x"],
                        "y": hit_target["y"],
                        "scale": hit_target["scale"],
                        "flash_hit": 0.4
                    })
                    
                    self._hits += 1
                    
                    # Trigger extreme bite juice (shakes, time freeze, audio hit)
                    self._shake_amount = 22.0
                    self._screen_flash = 0.25
                    self._hitstop_timer = 0.08

                    if self._bite_sounds:
                        random.choice(self._bite_sounds).play()
                    elif app.game_instance and hasattr(app.game_instance, "snd_hit") and app.game_instance.snd_hit:
                        app.game_instance.snd_hit.play()
                    
                    # Trigger bite splatter/explosions
                    self._spawn_chomp_effects(hit_target["x"], hit_target["y"])
                    
                    # Spawn a new target to replace it at the end of the chain
                    if self._targets:
                        last_t = self._targets[-1]
                        nx, ny = self._generate_next_position(last_t["x"], last_t["y"])
                    else:
                        nx, ny = random.uniform(0.15, 0.85), random.uniform(0.20, 0.80)
                    self._add_new_target(nx, ny)

        # Update particles (with gravity for bones)
        for p in self._particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p.get("type") == "bone":
                p["vy"] += 0.95 * dt # Gravity pull
                p["angle"] += p["rot_speed"] * dt
            p["life"] -= dt
        self._particles = [p for p in self._particles if p["life"] > 0]

        # Update floating texts
        for ft in self._floating_texts:
            ft["life"] -= dt
            ft["y"] -= 0.06 * dt  # slow drift up
        self._floating_texts = [ft for ft in self._floating_texts if ft["life"] > 0]

    def _spawn_chomp_effects(self, tx, ty):
        # 1. Add drift text
        self._floating_texts.append({
            "text": random.choice(["NHAC!", "CHOMP!", "NHOQUE!", "CRUNCH!"]),
            "x": tx,
            "y": ty - 0.05,
            "life": 0.6,
            "max_life": 0.6
        })

        # 2. Spawn red juicy meat chunk particles
        for _ in range(8):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(0.1, 0.3)
            self._particles.append({
                "type": "meat",
                "x": tx,
                "y": ty,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": random.uniform(0.4, 0.7),
                "max_life": 0.7,
                "size": random.uniform(6.0, 11.0)
            })

        # 3. Spawn white glowing bone that flies away under gravity
        self._particles.append({
            "type": "bone",
            "x": tx,
            "y": ty,
            "vx": random.uniform(-0.15, 0.15),
            "vy": random.uniform(-0.55, -0.35),
            "life": 0.8,
            "max_life": 0.8,
            "angle": 0.0,
            "rot_speed": random.uniform(270, 540)
        })

        # 4. Spawn orange neon sparks/embers
        for _ in range(8):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(0.12, 0.45)
            self._particles.append({
                "type": "spark",
                "x": tx,
                "y": ty,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": random.uniform(0.3, 0.6),
                "max_life": 0.6,
                "color": random.choice([(255, 90, 0), (255, 210, 0), (200, 40, 20)])
            })

    def evaluate(self):
        if self._hits >= 12:
            return "excellent"
        elif self._hits >= 6:
            return "good"
        else:
            return "poor"

    def draw_custom_cursor(self, painter, hx_norm, hy_norm, width, height, scale):
        # We draw the custom jaw cursors directly inside paint() to easily support multiple hand cursors!
        pass

    def _draw_jaw_cursor(self, painter, hx_norm, hy_norm, width, height, scale, jaw_gap):
        """Draws the retro-cyber dinosaur jaws at a specific coordinate."""
        from PySide6.QtCore import QPointF, QPoint, Qt
        from PySide6.QtGui import QColor, QPen, QBrush, QPolygon, QPainter

        hx = int(hx_norm * width)
        hy = int(hy_norm * height)
        gap = int(jaw_gap * scale)
        w_jaw = int(35 * scale)
        t_height = int(12 * scale)

        # 1. Draw mechanical connections/hinges (robotic feel)
        painter.setRenderHint(QPainter.Antialiasing)
        pen_connect = QPen(QColor(150, 150, 150, 90), 2.0 * scale)
        painter.setPen(pen_connect)
        painter.drawLine(hx - w_jaw - int(10 * scale), hy - gap, hx - w_jaw - int(10 * scale), hy + gap)
        painter.drawLine(hx + w_jaw + int(10 * scale), hy - gap, hx + w_jaw + int(10 * scale), hy + gap)

        # 2. Draw glowing jaws (neon cyber red/orange)
        jaw_color = QColor(255, 60, 0)
        pen_jaw = QPen(jaw_color, 4.0 * scale)
        painter.setPen(pen_jaw)
        painter.setBrush(Qt.NoBrush)

        # Upper jaw base line
        painter.drawLine(hx - w_jaw, hy - gap, hx + w_jaw, hy - gap)
        # Lower jaw base line
        painter.drawLine(hx - w_jaw, hy + gap, hx + w_jaw, hy + gap)

        # 3. Draw Teeth (cyber glowing yellow)
        painter.setPen(Qt.NoPen)
        brush_teeth = QBrush(QColor(255, 200, 30, 220))
        painter.setBrush(brush_teeth)

        # Upper teeth pointing DOWN
        for offset in [-w_jaw + int(12 * scale), 0, w_jaw - int(12 * scale)]:
            poly = QPolygon([
                QPoint(hx + offset - int(6 * scale), hy - gap),
                QPoint(hx + offset + int(6 * scale), hy - gap),
                QPoint(hx + offset, hy - gap + t_height)
            ])
            painter.drawPolygon(poly)

        # Lower teeth pointing UP
        for offset in [-w_jaw + int(12 * scale), 0, w_jaw - int(12 * scale)]:
            poly = QPolygon([
                QPoint(hx + offset - int(6 * scale), hy + gap),
                QPoint(hx + offset + int(6 * scale), hy + gap),
                QPoint(hx + offset, hy + gap - t_height)
            ])
            painter.drawPolygon(poly)

        # 4. Electric white-cyan plasma spark when jaw is completely snapped shut
        if gap < int(10 * scale):
            pen_plasma = QPen(QColor(0, 240, 255, 230), 3.0 * scale)
            painter.setPen(pen_plasma)
            painter.drawLine(hx - w_jaw, hy, hx + w_jaw, hy)
            # draw small cross sparks
            for sx in [-w_jaw//2, 0, w_jaw//2]:
                painter.drawLine(hx + sx, hy - int(5*scale), hx + sx + int(3*scale), hy + int(5*scale))

    def paint(self, painter, width, height, scale):
        from PySide6.QtCore import QRectF, QPointF, Qt
        from PySide6.QtGui import QColor, QPen, QBrush, QFont, QRadialGradient

        elapsed = self._elapsed
        t = time.time()

        # ── Apply Screen Shake translation (Juice) ──
        if self._shake_amount > 0:
            dx = random.uniform(-self._shake_amount, self._shake_amount)
            dy = random.uniform(-self._shake_amount, self._shake_amount)
            painter.translate(dx, dy)

        # ── Paint Connection Lines (Chain Visual) ──
        if len(self._targets) > 1:
            pen_line = QPen(QColor(0, 240, 255, 130), 3.0 * scale, Qt.DashLine)
            painter.setPen(pen_line)
            for i in range(len(self._targets) - 1):
                t1 = self._targets[i]
                t2 = self._targets[i+1]
                x1, y1 = int(t1["x"] * width), int(t1["y"] * height)
                x2, y2 = int(t2["x"] * width), int(t2["y"] * height)
                painter.drawLine(x1, y1, x2, y2)

        # ── Fetch active hands list (usa cache do on_update — sem lock no paintEvent) ──
        hands_list = list(getattr(self, "_cached_hands", []))
        
        # Fallback to single hand / mouse
        if not hands_list:
            # Check cached cursor position
            hand_pos = None
            if hasattr(self, "_last_hand_pos"):
                hand_pos = self._last_hand_pos
            if hand_pos is None:
                from engine import app_core as app
                if app.game_instance and hasattr(app.game_instance, "_finger_pos_norm"):
                    hand_pos = app.game_instance._finger_pos_norm
            if hand_pos is not None:
                hands_list = [{"pos": hand_pos, "closed": False}]

        # Save first hand position for fallback cache
        if hands_list:
            self._last_hand_pos = hands_list[0]["pos"]

        # Find which active target is locked onto by any of the hands
        closest_lock_idx = -1
        closest_dist = float('inf')
        for idx, target in enumerate(self._targets):
            for hand in hands_list:
                h_pos = hand["pos"]
                if h_pos is not None:
                    dist = math.sqrt((h_pos[0] - target["x"])**2 + (h_pos[1] - target["y"])**2)
                    if dist <= HIT_RADIUS_NORM and dist < closest_dist:
                        closest_dist = dist
                        closest_lock_idx = idx

        # ── Paint Dead Targets (Fade-out hit animation) ──
        for dtg in self._dead_targets:
            cx = int(dtg["x"] * width)
            cy = int(dtg["y"] * height)
            base_r = int(TARGET_RADIUS_NORM * min(width, height) * dtg["scale"])

            # Hit feedback: fade out expanding green circle
            flash_t = 1.0 - (dtg["flash_hit"] / 0.4)
            expand_r = int(base_r * (1.0 + flash_t * 0.4))
            alpha = int(255 * (1.0 - flash_t))

            painter.setPen(QPen(QColor(35, 255, 120, alpha), 3 * scale))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), expand_r, expand_r)

        # ── Paint Active Targets ──
        for idx, target in enumerate(self._targets):
            tx, ty = target["x"], target["y"]
            cx = int(tx * width)
            cy = int(ty * height)
            base_r = int(TARGET_RADIUS_NORM * min(width, height) * target["scale"])
            if base_r <= 0:
                continue

            pulse = 0.95 + 0.15 * math.sin(t * 10.0 + idx)

            # Outer neon glow circle
            r_outer = int(base_r * (1.0 + 0.08 * math.sin(t * 8.0 + idx)))
            if idx == 0:
                glow_color = QColor(255, 210, 0, int(180 * pulse))
                pen_width = 3.5 * scale
            else:
                glow_color = QColor(255, 100, 0, int(130 * pulse))
                pen_width = 2.0 * scale

            painter.setPen(QPen(glow_color, pen_width))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r_outer, r_outer)

            # Draw target LOCK ON reticle if this target is locked
            if idx == closest_lock_idx:
                painter.setPen(QPen(QColor(0, 240, 255, 200), 2.0 * scale, Qt.DashLine))
                lock_r = int(base_r * (1.2 + 0.15 * math.sin(t * 16.0)))
                painter.drawEllipse(QPointF(cx, cy), lock_r, lock_r)
                
                font_lock = QFont("Bahnschrift", int(11 * scale), QFont.Bold)
                painter.setFont(font_lock)
                painter.setPen(QColor(0, 240, 255, 220))
                painter.drawText(QRectF(cx - 50, cy - base_r - 28*scale, 100, 20*scale), Qt.AlignCenter, "◄ LOCK ON ►")

            # Draw steak shape
            # Bone sticking out
            painter.setPen(QPen(QColor(245, 245, 245), 2.5 * scale))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            bone_w = int(14 * scale * target["scale"])
            bone_h = int(32 * scale * target["scale"])
            
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(35)
            if bone_w > 0 and bone_h > 0:
                painter.drawRoundedRect(QRectF(-bone_w//2, -base_r - bone_h//2, bone_w, bone_h), 4*scale, 4*scale)
                painter.drawEllipse(QPointF(-int(6*scale*target["scale"]), -base_r - bone_h//2), int(7*scale*target["scale"]), int(7*scale*target["scale"]))
                painter.drawEllipse(QPointF(int(6*scale*target["scale"]), -base_r - bone_h//2), int(7*scale*target["scale"]), int(7*scale*target["scale"]))
            painter.restore()

            # Red meat slice
            meat_r = int(base_r * 0.85)
            if meat_r > 0:
                grad = QRadialGradient(cx, cy, meat_r)
                if idx == 0:
                    grad.setColorAt(0.0, QColor(255, 50, 50, 240))
                    grad.setColorAt(0.7, QColor(200, 20, 20, 230))
                    grad.setColorAt(1.0, QColor(130, 10, 10, 220))
                else:
                    grad.setColorAt(0.0, QColor(190, 20, 20, 240))
                    grad.setColorAt(0.7, QColor(140, 10, 10, 230))
                    grad.setColorAt(1.0, QColor(90, 5, 5, 220))

                painter.setPen(QPen(QColor(230, 220, 190), 2.0 * scale)) # fat outline
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(QPointF(cx, cy), meat_r, meat_r)

                # Inner fat marble lines
                painter.setPen(QPen(QColor(240, 230, 200, 140), 1.5 * scale))
                painter.drawLine(cx - int(10*scale*target["scale"]), cy - int(5*scale*target["scale"]), cx + int(10*scale*target["scale"]), cy + int(10*scale*target["scale"]))
                painter.drawLine(cx - int(5*scale*target["scale"]), cy + int(10*scale*target["scale"]), cx + int(8*scale*target["scale"]), cy - int(8*scale*target["scale"]))

        # ── Paint Particles (bone & chunks gravity physics) ──
        for p in self._particles:
            alpha = int(255 * (p["life"] / p["max_life"]))
            px = int(p["x"] * width)
            py = int(p["y"] * height)
            
            if p.get("type") == "bone":
                painter.save()
                painter.translate(px, py)
                painter.rotate(p["angle"])
                
                painter.setPen(QPen(QColor(240, 240, 240, alpha), 1.5 * scale))
                painter.setBrush(QBrush(QColor(255, 255, 255, alpha)))
                
                bone_w = int(6 * scale)
                bone_h = int(20 * scale)
                painter.drawRect(-bone_w//2, -bone_h//2, bone_w, bone_h)
                r_knob = int(5 * scale)
                painter.drawEllipse(QPointF(-int(3*scale), -bone_h//2), r_knob, r_knob)
                painter.drawEllipse(QPointF(int(3*scale), -bone_h//2), r_knob, r_knob)
                painter.drawEllipse(QPointF(-int(3*scale), bone_h//2), r_knob, r_knob)
                painter.drawEllipse(QPointF(int(3*scale), bone_h//2), r_knob, r_knob)
                
                painter.restore()
            elif p.get("type") == "meat":
                r = int(p["size"] * (p["life"] / p["max_life"]) * scale)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(210, 30, 30, alpha)))
                painter.drawRoundedRect(QRectF(px - r, py - r, r*2, r*2), r//2, r//2)
            else:
                r = int(max(2.0, 6.0 * (p["life"] / p["max_life"])) * scale)
                c = p["color"]
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(c[0], c[1], c[2], alpha)))
                painter.drawEllipse(QPointF(px, py), r, r)

        # ── Paint Floating Drift Texts ──
        for ft in self._floating_texts:
            alpha = int(255 * (ft["life"] / ft["max_life"]))
            font = QFont("Bahnschrift", int(24 * scale), QFont.Bold)
            painter.setFont(font)
            painter.setPen(QColor(255, 215, 0, alpha))
            px = int(ft["x"] * width)
            py = int(ft["y"] * height)
            painter.drawText(QRectF(px - 100, py - 20, 200, 40), Qt.AlignCenter, ft["text"])

        # ── Paint Full-Screen Damage/Hit Flash (Juice) ──
        if self._screen_flash > 0:
            alpha_flash = int((self._screen_flash / 0.25) * 55)
            painter.fillRect(0, 0, width, height, QColor(0, 255, 120, alpha_flash))

        # ── Paint Jaw Cursors (Two mouths!) ──
        for idx, hand in enumerate(hands_list):
            h_pos = hand["pos"]
            if h_pos is not None:
                # Ensure jaw_gaps has a slot for this hand
                while len(self._jaw_gaps) <= idx:
                    self._jaw_gaps.append(40.0)
                self._draw_jaw_cursor(painter, h_pos[0], h_pos[1], width, height, scale, self._jaw_gaps[idx])

        # ── Paint Score HUD ──
        font = QFont("Bahnschrift", int(22 * scale), QFont.Bold)
        painter.setFont(font)
        
        if self._hits >= 12:
            rating_text = "EXCELENTE!"
            rating_color = QColor(35, 255, 120)
        elif self._hits >= 6:
            rating_text = "BOM!"
            rating_color = QColor(255, 200, 30)
        else:
            rating_text = "RUIM"
            rating_color = QColor(255, 60, 60)
            
        score_text = f"PRESAS COMIDAS: {self._hits}  ({rating_text})"
        painter.setPen(rating_color)
        painter.drawText(QRectF(0, 24 * scale, width, 40 * scale), Qt.AlignCenter, score_text)




# combat/minigames/target_aim/attack.py
# ═══════════════════════════════════════════════════════════════════════
# Animação de ataque 3D para Jurassic Bite (minijogo target_aim)
# ═══════════════════════════════════════════════════════════════════════

async def execute_jurassic_bite_attack(robot, target, ability, final_damage, camera, ctx):
    # O dano é aplicado DENTRO da sequência de movimento no momento certo
    await player_attack_sequence_jurassic_bite(robot, target, ability, final_damage, camera, ctx)

from game.champions.robot_base import DB_MOV, PL_MOV, DB_TURN, PL_TURN, WAIT_MOV, DELAY, DB_ATTACK, PL_ATTACK, GET_CHOICE, PLAY_SOUND

async def player_attack_sequence_jurassic_bite(robot, target, ability, final_damage, camera, ctx):
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║   SEQUÊNCIA DE MOVIMENTO — JURASSIC BITE (DinoByte)             ║
    # ╚══════════════════════════════════════════════════════════════════╝
    # Funções disponíveis:
    #   from game.champions.robot_base import (DB_MOV, PL_MOV, DB_TURN,
    #       PL_TURN, WAIT_MOV, DELAY, DB_ATTACK, PL_ATTACK, GET_CHOICE)
    #
    #   await DB_MOV(ctx, "FRENTE", 3)   → DinoByte anda 3 tiles para frente
    #   await DB_MOV(ctx, "TRAS", 2)     → DinoByte anda 2 tiles para trás
    #   await DB_TURN(ctx, "DIREITA")    → DinoByte vira 90° à direita
    #   await DB_TURN(ctx, "FULL")       → DinoByte gira 360° completo
    #   await PL_MOV / PL_TURN          → mesmas funções para PenLinux
    #   await WAIT_MOV()                → aguarda término do movimento
    #   await DELAY(segundos)           → pausa por N segundos
    # ─────────────────────────────────────────────────────────────────
    # Programar aqui:

        # Exemplo prático de uma sequência tática (Combo Tail Quake):
    # 1. Avança rapidamente em direção ao inimigo
    await DB_MOV(ctx, "FRENTE", 2)
    await WAIT_MOV()   
    
    # 2. Executa um giro completo de 360 graus para ganhar momento (Tail Quake)
    await DB_TURN(ctx, "FULL")
    await WAIT_MOV()   
    
    # 3. Executa o ataque no alvo com o dano final calculado do minigame
    await PLAY_SOUND(ctx, f"assets/sounds/dinobyte/bytefinal.wav")
    await DB_ATTACK(ctx, "MELEE", final_damage)
    await WAIT_MOV()
    
    # 4. Recua para a posição defensiva
    await DB_MOV(ctx, "TRAS", 2) 
    await WAIT_MOV()

    return True
