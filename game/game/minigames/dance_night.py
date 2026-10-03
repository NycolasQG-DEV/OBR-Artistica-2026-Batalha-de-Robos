import os
import random
import time
import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPen, QBrush, QPixmap
from game.minigames.base_minigame import BaseAttackMinigame
from game.config.battle import MINIGAME_DURATION

GESTURE_SPRITES = {
    1: "assets/textures/pose_right_up.png",
    2: "assets/textures/pose_left_up.png",
    3: "assets/textures/pose_both_up.png",
    4: "assets/textures/pose_neutral.png",
    5: "assets/textures/pose_crossed.png"
}

SUCCESS_TEXTS = ["Beautiful!", "Nice!", "Awesome!", "Perfect!", "Great!", "Groovy!"]

class DanceNightMinigame(BaseAttackMinigame):
    instruction_text = " DANCE NIGHT!\nImite as poses do Stickman na tela!"
    instruction_icon = ""
    explanation_sound = ""
    duration = 10.0  # seconds of active gameplay

    def on_start(self):
        # Enable pose detection in cv_input
        from engine import app_core as app
        if app.game_instance and app.game_instance.cv_input:
            app.game_instance.cv_input.pose_detection_enabled = True

        self._hits = 0
        self._pose_atual = random.randint(1, 5)
        self._last_pose = self._pose_atual

        self._pose_time_limit = 3.0  # seconds to complete the pose
        self._pose_timer = self._pose_time_limit
        self._pose_progress = 0.0

        # Feedback variables
        self._feedback_text = ""
        self._feedback_color = QColor(0, 0, 0, 0)
        self._feedback_timer = 0.0

        # Reference to latest landmarks
        self._latest_landmarks = None

        # Transition variables
        self._old_pose = None
        self._pose_transition = 1.0  # 1.0 means transition complete

    def on_finish(self):
        # Disable pose detection in cv_input
        from engine import app_core as app
        if app.game_instance and app.game_instance.cv_input:
            app.game_instance.cv_input.pose_detection_enabled = False
            app.game_instance.cv_input.latest_pose_landmarks = None

    def on_update(self, hand_pos, hand_closed, dt):
        # Retrieve latest pose landmarks from cv_input
        from engine import app_core as app
        landmarks = None
        if app.game_instance and app.game_instance.cv_input:
            landmarks = app.game_instance.cv_input.latest_pose_landmarks
        self._latest_landmarks = landmarks

        # Update pose timer
        self._pose_timer = max(0.0, self._pose_timer - dt)

        # Decay feedback timer
        if self._feedback_timer > 0:
            self._feedback_timer = max(0.0, self._feedback_timer - dt)

        # Update transition timer
        if self._pose_transition < 1.0:
            self._pose_transition = min(1.0, self._pose_transition + dt * 3.5)

        # Check pose detection
        pose_detected = None
        if landmarks:
            pose_detected = self.detect_gesture(landmarks)
        elif hand_closed:
            pose_detected = self._pose_atual

        # Progress tracking
        if pose_detected == self._pose_atual:
            self._pose_progress = min(1.0, self._pose_progress + 6.0 * dt)
        else:
            self._pose_progress = max(0.0, self._pose_progress - 2.5 * dt)

        # Success / Fail evaluation
        if self._pose_progress >= 1.0:
            # Success!
            self._hits += 1
            self._feedback_text = random.choice(SUCCESS_TEXTS)
            self._feedback_color = QColor(35, 255, 120)  # Green
            self._feedback_timer = 0.6

            # Accelerate the game: reduce time limit
            self._pose_time_limit = max(1.5, self._pose_time_limit - 0.25)
            self._next_pose()

        elif self._pose_timer <= 0:
            # Fail (Miss!)
            self._hits = max(0, self._hits - 1)
            self._feedback_text = "Miss"
            self._feedback_color = QColor(255, 50, 50)  # Red
            self._feedback_timer = 0.6

            self._next_pose()

    def _next_pose(self):
        self._old_pose = self._pose_atual
        self._pose_transition = 0.0
        # Pick a different pose
        next_p = random.randint(1, 5)
        while next_p == self._last_pose:
            next_p = random.randint(1, 5)
        self._pose_atual = next_p
        self._last_pose = next_p

        # Reset states for the new pose
        self._pose_timer = self._pose_time_limit
        self._pose_progress = 0.0

    def detect_gesture(self, landmarks):
        if len(landmarks) < 25:
            return None

        ombro_d = landmarks[12]
        cot_d   = landmarks[14]
        punho_d = landmarks[16]

        ombro_e = landmarks[11]
        cot_e   = landmarks[13]
        punho_e = landmarks[15]

        hip_d   = landmarks[24]
        hip_e   = landmarks[23]

        # Crossed arms detection (in the chest region)
        chest_top = min(ombro_d.y, ombro_e.y) - 0.05
        chest_bottom = max(hip_d.y, hip_e.y) + 0.05
        in_chest_y = (chest_top < punho_d.y < chest_bottom) and (chest_top < punho_e.y < chest_bottom)

        # Horizontal crossover check
        is_crossed_x = False
        if ombro_e.x < ombro_d.x:
            is_crossed_x = (punho_e.x > punho_d.x)
        else:
            is_crossed_x = (punho_d.x > punho_e.x)

        dist_wrists = math.hypot(punho_d.x - punho_e.x, punho_d.y - punho_e.y)
        is_overlapping = (dist_wrists < 0.09)

        crossed_arms = (is_crossed_x or is_overlapping) and in_chest_y

        if crossed_arms:
            return 5

        # Check height of right vs left arm using the highest joint of each arm (wrist or elbow)
        val_d = min(punho_d.y, cot_d.y)
        val_e = min(punho_e.y, cot_e.y)
        
        # Compare relative heights (smaller y is higher up)
        diff = val_d - val_e
        
        if diff > 0.10:
            # Left hand (anatomical) is higher (smaller y), which corresponds to physical right hand on screen-right.
            return 1  # Right hand raised
        elif diff < -0.10:
            # Right hand (anatomical) is higher (smaller y), which corresponds to physical left hand on screen-left.
            return 2  # Left hand raised
        else:
            # Both hands are at a similar height
            # Check if they are both above the shoulders
            right_up = (val_d < ombro_d.y)
            left_up = (val_e < ombro_e.y)
            
            if right_up and left_up:
                return 3  # Both hands raised
            else:
                return 4  # Both hands down
        return None

    def get_legend(self, pose):
        legends = {
            1: "Levante a mão direita!",
            2: "Levante a mão esquerda!",
            3: "Levante as duas mãos!",
            4: "Abaixe as mãos!",
            5: "Cruze os braços!"
        }
        return legends.get(pose, "")

    def evaluate(self) -> str:
        if self._hits >= 5:
            return "excellent"
        elif self._hits >= 2:
            return "good"
        else:
            return "poor"

    def draw_stickman(self, painter, cx, cy, pose, scale, alpha=255):
        pen = QPen(QColor(255, 255, 255, alpha), int(6 * scale), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        corpo = int(80 * scale)
        braco = int(55 * scale)
        perna = int(65 * scale)

        # Head
        head_radius = int(18 * scale)
        head_pen = QPen(QColor(255, 255, 255, alpha), int(6 * scale), Qt.SolidLine)
        painter.setPen(head_pen)
        painter.drawEllipse(QPointF(cx, cy - corpo // 2 - head_radius), head_radius, head_radius)

        # Torso
        painter.drawLine(cx, cy - corpo // 2, cx, cy + corpo // 2)

        # Legs
        painter.drawLine(cx, cy + corpo // 2, cx - int(perna * 0.7), cy + corpo // 2 + int(perna * 0.7))
        painter.drawLine(cx, cy + corpo // 2, cx + int(perna * 0.7), cy + corpo // 2 + int(perna * 0.7))

        # Arms
        shoulder_y = cy - corpo // 3
        if pose == 1:
            # Right arm (screen right) up, left arm (screen left) down
            painter.drawLine(cx, shoulder_y, cx + int(braco * 0.7), shoulder_y - int(braco * 0.7))
            painter.drawLine(cx, shoulder_y, cx - int(braco * 0.7), shoulder_y + int(braco * 0.5))
        elif pose == 2:
            # Left arm (screen left) up, right arm (screen right) down
            painter.drawLine(cx, shoulder_y, cx - int(braco * 0.7), shoulder_y - int(braco * 0.7))
            painter.drawLine(cx, shoulder_y, cx + int(braco * 0.7), shoulder_y + int(braco * 0.5))
        elif pose == 3:
            # Both arms up
            painter.drawLine(cx, shoulder_y, cx - int(braco * 0.7), shoulder_y - int(braco * 0.7))
            painter.drawLine(cx, shoulder_y, cx + int(braco * 0.7), shoulder_y - int(braco * 0.7))
        elif pose == 4:
            # Neutral/down
            painter.drawLine(cx, shoulder_y, cx - int(braco * 0.8), shoulder_y + int(braco * 0.2))
            painter.drawLine(cx, shoulder_y, cx + int(braco * 0.8), shoulder_y + int(braco * 0.2))
        elif pose == 5:
            # Crossed arms
            painter.drawLine(cx, shoulder_y, cx - int(braco * 0.5), shoulder_y + int(braco * 0.2))
            painter.drawLine(cx - int(braco * 0.5), shoulder_y + int(braco * 0.2), cx + int(braco * 0.4), shoulder_y + int(braco * 0.2))
            painter.drawLine(cx, shoulder_y, cx + int(braco * 0.5), shoulder_y + int(braco * 0.1))
            painter.drawLine(cx + int(braco * 0.5), shoulder_y + int(braco * 0.1), cx - int(braco * 0.4), shoulder_y + int(braco * 0.1))

    def paint(self, painter, width: int, height: int, scale: float):
        cx = width // 2
        cy = height // 2

        # 1. Circular scanning boundary around the center
        radius = int(120 * scale)
        painter.setPen(QPen(QColor(255, 255, 255, 30), int(2 * scale), Qt.DashLine))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 2. Hold progress arc around the stickman
        if self._pose_progress > 0:
            progress_pen = QPen(QColor(35, 255, 120), int(5 * scale))
            painter.setPen(progress_pen)
            span_angle = int(360 * self._pose_progress * 16)
            painter.drawArc(cx - radius, cy - radius, radius * 2, radius * 2, 90 * 16, -span_angle)

        # 3. Draw active stickman (or sprite if exists) with transition cross-fade
        if self._pose_transition < 1.0 and self._old_pose is not None:
            # Draw old pose fading out
            alpha_out = int(255 * (1.0 - self._pose_transition))
            self.draw_pose_helper(painter, cx, cy, self._old_pose, scale, alpha_out)
            
            # Draw new pose fading in
            alpha_in = int(255 * self._pose_transition)
            self.draw_pose_helper(painter, cx, cy, self._pose_atual, scale, alpha_in)
        else:
            self.draw_pose_helper(painter, cx, cy, self._pose_atual, scale, 255)

        # 4. Timer bar for active gesture
        bar_w = int(width * 0.5)
        bar_h = int(10 * scale)
        bar_x = (width - bar_w) // 2
        bar_y = int(height * 0.74)
        
        # Background bar
        painter.fillRect(bar_x, bar_y, bar_w, bar_h, QColor(255, 255, 255, 20))
        # Filled time bar
        frac = self._pose_timer / self._pose_time_limit
        time_color = QColor(0, 236, 255) if frac > 0.4 else QColor(255, 120, 50)
        painter.fillRect(bar_x, bar_y, int(bar_w * frac), bar_h, time_color)

        # 5. Legend under the stickman
        legend = self.get_legend(self._pose_atual)
        font = QFont("Bahnschrift", int(22 * scale), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(0, height * 0.78, width, height * 0.1), Qt.AlignCenter, legend)

        # 6. Score (hits) counter
        score_text = f"HITS: {self._hits}"
        score_font = QFont("Consolas", int(18 * scale), QFont.Bold)
        painter.setFont(score_font)
        painter.setPen(QColor(0, 236, 255))
        painter.drawText(QRectF(width * 0.05, height * 0.05, width * 0.2, height * 0.1), Qt.AlignLeft, score_text)

        # 7. Success / Fail Border Flash and Floating Text
        if self._feedback_timer > 0:
            alpha = int(255 * (self._feedback_timer / 0.6))
            flash_color = QColor(self._feedback_color.red(), self._feedback_color.green(), self._feedback_color.blue(), int(alpha * 0.35))
            
            # Thick outer border flash
            border_pen = QPen(flash_color, int(15 * scale))
            painter.setPen(border_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(0, 0, width, height)

            # Floating feedback word
            text_color = QColor(self._feedback_color.red(), self._feedback_color.green(), self._feedback_color.blue(), alpha)
            feedback_font = QFont("Bahnschrift", int(40 * scale), QFont.Bold)
            painter.setFont(feedback_font)
            painter.setPen(text_color)
            painter.drawText(QRectF(0, height * 0.12, width, height * 0.1), Qt.AlignCenter, self._feedback_text)

    def draw_pose_helper(self, painter, cx, cy, pose, scale, alpha):
        sprite_path = GESTURE_SPRITES.get(pose, "")
        if sprite_path and os.path.exists(sprite_path):
            pixmap = QPixmap(sprite_path)
            sprite_size = int(180 * scale)
            painter.setOpacity(alpha / 255.0)
            painter.drawPixmap(cx - sprite_size // 2, cy - sprite_size // 2, sprite_size, sprite_size, pixmap)
            painter.setOpacity(1.0)
        else:
            self.draw_stickman(painter, cx, cy, pose, scale, alpha)


# game/minigames/dance_night/attack.py
# ═══════════════════════════════════════════════════════════════════════
# Animação de ataque 3D para Dance Night (minijogo dance_night)
# ═══════════════════════════════════════════════════════════════════════

async def execute_dance_night_attack(robot, target, ability, final_damage, camera, ctx):
    from game.champions.robot_base import PL_ATTACK, PL_TURN, PL_MOV, WAIT_MOV

    rating = ctx.mini_game_result
    if isinstance(ctx.mini_game_result, dict):
        rating = ctx.mini_game_result.get("rating", "good")

    dance_hits = getattr(ctx, "dance_hits", 0)

    if dance_hits == 0:
        ctx.create_floating(robot.v_tx, robot.v_ty, "FAIL! 0 HITS", (1.0, 0.2, 0.2, 1.0), size=1.1)
    else:
        if rating == "excellent":
            ctx.create_floating(robot.v_tx, robot.v_ty, "DANCE MASTER!", (0.0, 1.0, 0.5, 1.0), size=1.5)
        elif rating == "good":
            ctx.create_floating(robot.v_tx, robot.v_ty, "NICE RHYTHM!", (0.0, 0.9, 1.0, 1.0), size=1.3)
        else:
            ctx.create_floating(robot.v_tx, robot.v_ty, "OUT OF SYNC!", (1.0, 0.2, 0.2, 1.0), size=1.1)

        if final_damage > 0:
            await PL_ATTACK(ctx, final_damage)
            await WAIT_MOV()

    # ── Sequência pós-minigame ──────────────────────────────────────────
    # 1. Girar 90° de volta para encarar o boss de frente
    await PL_TURN(ctx, "DIREITA")
    await WAIT_MOV()

    # 2. Câmera retorna para a visão normal de combate
    if camera:
        camera.enter_battle_mode()

    # 3. Robô recua 1 tile para trás (retornando à posição inicial)
    await PL_MOV(ctx, "TRAS", 1)
    await WAIT_MOV()


async def player_attack_sequence_dance_night(robot, target, ability, final_damage, camera, ctx):
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║   SEQUÊNCIA DE MOVIMENTO — DANCE NIGHT (PenLinux)               ║
    # ╚══════════════════════════════════════════════════════════════════╝
    from game.champions.robot_base import PL_MOV, PL_TURN, WAIT_MOV, DELAY
    from engine.render.geometry import grid_to_world
    from panda3d.core import Point3

    # 1. PenLinux anda 1 tile para frente
    await PL_MOV(ctx, "FRENTE", 1)
    await WAIT_MOV()

    # 2. Gira 90° para a esquerda
    await PL_TURN(ctx, "ESQUERDA")
    await WAIT_MOV()

    # 3. Câmera dá um close-in nele de frente
    if camera:
        wp = grid_to_world(robot.v_tx, robot.v_ty)
        camera._mode = camera.MODE_ACTION
        # Enquadramento de frente: elevação ajustada (z = 1.35) e recuado para trás (dist = 10.0)
        camera._target_center = Point3(wp.getX(), wp.getY(), 1.35)
        camera._target_heading = 90.0
        camera._target_dist = 10.0       # Recuado para trás
        camera._target_pitch = -8.0     # Inclinação suave de frente
        camera._target_fov = 42.0
        camera.set_camera_speed('fast')

    await DELAY(1.5)

    return True
