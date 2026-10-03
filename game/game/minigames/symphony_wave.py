# game/minigames/symphony_wave.py
# ═══════════════════════════════════════════════════════════════════════
# Minigame "NOTAS MUSICAIS / SYMPHONY WAVE" — PenLinux  (3 FAIXAS)
# ═══════════════════════════════════════════════════════════════════════
# 3 faixas: 0 = Esquerda, 1 = Centro (base), 2 = Direita
# O PenLinux começa no centro (lane 1).
# Cursor na ESQUERDA da tela (<0.38) → lane 0  →  PL_MOV FRENTE 1
# Cursor no CENTRO da tela  (0.38-0.62) → lane 1  →  sem movimento / retorno
# Cursor na DIREITA da tela (>0.62) → lane 2  →  PL_MOV TRAS 1
# Range máximo: 1 tile para frente OU 1 tile para trás da posição inicial.
# _tile_offset: -1 (frente/esquerda), 0 (centro), +1 (ré/direita)
# ═══════════════════════════════════════════════════════════════════════

import random
import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from game.minigames.base_minigame import BaseAttackMinigame
from game.config.battle import MINIGAME_DURATION

# Posições X normalizadas das 3 faixas na tela
LANE_X = [0.25, 0.50, 0.75]   # lane 0 = 25%, lane 1 = 50%, lane 2 = 75%


class SymphonyWaveMinigame(BaseAttackMinigame):
    instruction_text = "NOTAS MUSICAIS!\nIncline a cabeca para esquerda, centro ou direita\npara coletar as notas musicais em 3 faixas!"
    instruction_icon = "?"
    explanation_sound = "assets/sounds/penlinux/minigames/symphony_wave.wav"
    duration = 10.0

    def on_start(self):
        self._notes = []
        self._note_counter = 0
        self._hits = 0
        self._shattered = []

        # lane 1 = Centro (posicao inicial do robo no mundo fisico)
        # _tile_offset: deslocamento em relacao ao centro
        #   -1 = andou FRENTE 1 (faixa esquerda)
        #    0 = no centro
        #   +1 = andou TRAS 1  (faixa direita)
        self._lane = 1
        self._tile_offset = 0
        self._is_shifting = False
        self._screen_flash = 0.0
        self._snd_note = None

        try:
            from engine import app_core as app
            if app.game_instance and hasattr(app.game_instance, "cv_input") and app.game_instance.cv_input:
                app.game_instance.cv_input.face_detection_enabled = True
            if app.game_instance and hasattr(app.game_instance, "loader"):
                self._snd_note = app.game_instance.loader.loadSfx("assets/sounds/select.wav")
        except Exception:
            pass

        self._spawn_note()

    def _play_note_sound(self):
        if self._snd_note:
            try:
                self._snd_note.play()
            except Exception:
                pass

    def _spawn_note(self):
        symbols = ["🎵", "🎶", "🎼", "♪", "♫"]
        lane = random.choice([0, 1, 2])
        # Decreased falling speed for a smoother gameplay
        speed = random.uniform(0.18, 0.28)
        self._notes.append({
            "id": self._note_counter,
            "lane": lane,
            "y": 0.05,
            "speed": speed,
            "symbol": random.choice(symbols),
            "color": random.choice([
                QColor(0, 240, 255),
                QColor(255, 100, 220),
                QColor(255, 220, 0),
                QColor(0, 255, 150),
                QColor(255, 150, 50),
            ])
        })
        self._note_counter += 1

    def _lane_from_cursor(self, cursor_x):
        """Converte posicao X normalizada do cursor em lane desejada (0, 1 ou 2)."""
        if cursor_x < 0.38:
            return 0    # Esquerda da tela -> faixa esquerda (FRENTE 1)
        elif cursor_x > 0.62:
            return 2    # Direita da tela  -> faixa direita  (TRAS 1)
        else:
            return 1    # Centro da tela   -> faixa central  (sem mover)

    def update(self, hand_pos: tuple | None, hand_closed: bool, dt: float):
        if not self._started or self._finished:
            return

        import time
        self._elapsed = time.time() - self._start_time

        if self._elapsed >= self.duration:
            # O minijogo SO pode ser considerado finalizado quando o robô NÃO estiver
            # no meio de uma transição de tile (aguardando o OK do serial)
            from engine import app_core as app
            from game.champions.robot_base import _DSL_TASKS
            b = app.game_instance.battle if app.game_instance else None
            pr = b.player_robot if b else None

            runner_busy = not b._runner.is_done if (b and hasattr(b, "_runner") and b._runner) else False
            is_shifting = getattr(self, "_is_shifting", False)
            is_moving = getattr(pr, "is_moving", False) if pr else False
            has_pending_tasks = len(_DSL_TASKS) > 0

            # Se ainda houver movimento físico em andamento, não encerra até o OK ser recebido
            if not is_shifting and not runner_busy and not is_moving and not has_pending_tasks:
                self._finished = True
                self._result = self.evaluate()
                self.on_finish()
                return
            else:
                # O tempo acabou: não processa novos movimentos no on_update, apenas aguarda a conclusão do atual
                return

        self.on_update(hand_pos, hand_closed, dt)

    def on_finish(self):
        super().on_finish()
        try:
            from engine import app_core as app
            if app.game_instance and hasattr(app.game_instance, "cv_input") and app.game_instance.cv_input:
                app.game_instance.cv_input.face_detection_enabled = False
        except Exception:
            pass

    def on_update(self, hand_pos, hand_closed, dt):
        if self._screen_flash > 0:
            self._screen_flash = max(0.0, self._screen_flash - dt * 2.0)

        # 1. Spawner (max 4 notas simultaneas para dar mais espacamento)
        if len(self._notes) < 4 and random.random() < dt * 1.6:
            self._spawn_note()


        # 2. Move notas para baixo
        for n in self._notes:
            n["y"] += n["speed"] * dt
        self._notes = [n for n in self._notes if n["y"] <= 0.95]

        # 3. Leitura do cursor — BLOQUEADA ate o "OK" serial do tile anterior
        from engine import app_core as app
        from game.champions.robot_base import _DSL_TASKS
        b = app.game_instance.battle if app.game_instance else None
        pr = b.player_robot if b else None

        runner_busy = not b._runner.is_done if (b and hasattr(b, "_runner") and b._runner) else False
        is_shifting = getattr(self, "_is_shifting", False)
        is_moving = getattr(pr, "is_moving", False) if pr else False
        has_pending_tasks = len(_DSL_TASKS) > 0

        if not is_shifting and not runner_busy and not is_moving and not has_pending_tasks:
            cursor_x = None

            # Prioridade 1: Rastreamento direto de cabeça/face via cv_input
            if app.game_instance and hasattr(app.game_instance, "cv_input") and app.game_instance.cv_input:
                cv = app.game_instance.cv_input
                cv.face_detection_enabled = True
                if hasattr(cv, "get_head_position"):
                    fx, _ = cv.get_head_position()
                    if fx is not None:
                        cursor_x = fx
                if cursor_x is None and hasattr(cv, "face_x") and cv.face_x is not None:
                    cursor_x = float(cv.face_x)

            # Prioridade 2: Posição do cursor no Panda3D (que recebe face_x quando cv é ativo)
            if cursor_x is None and app.game_instance and hasattr(app.game_instance, "_finger_pos_norm"):
                cpos = app.game_instance._finger_pos_norm
                if cpos and cpos[0] is not None:
                    cursor_x = cpos[0]

            if cursor_x is None and hand_pos and hand_pos[0] is not None:
                cursor_x = hand_pos[0]

            if cursor_x is not None:
                desired_lane = self._lane_from_cursor(cursor_x)

                if desired_lane != self._lane:
                    # Calcula o delta com base na posicao FISICA atual (_tile_offset)
                    # Nao atualiza _tile_offset aqui — so sera atualizado apos o WAIT_MOV confirmar
                    current_offset = self._tile_offset   # posicao fisica real
                    target_offset  = desired_lane - 1    # -1, 0 ou +1

                    # Clampa para range valido e limita a 1 tile por comando
                    delta = max(-1, min(1, target_offset - current_offset))
                    if delta == 0:
                        # Ja esta na posicao alvo
                        self._lane = desired_lane
                    else:
                        new_lane = (current_offset + delta) + 1   # lane apos o passo
                        self._lane = new_lane
                        self._is_shifting = True

                        if b and hasattr(b, "_runner") and b._runner:
                            direction = "TRAS" if delta > 0 else "FRENTE"
                            b._runner.start(self._do_robot_shift(b, direction, abs(delta), delta))
                        else:
                            self._is_shifting = False


        # 4. Coleta de notas na faixa atual
        collected = set()
        for n in self._notes:
            if n["lane"] == self._lane and 0.68 <= n["y"] <= 0.90:
                collected.add(n["id"])
                self._hits += 1
                self._play_note_sound()
                self._screen_flash = 0.3
                self._create_note_shatter(n["lane"], n["y"], n["color"])

        if collected:
            self._notes = [n for n in self._notes if n["id"] not in collected]

        # 5. Particulas
        for s in self._shattered:
            s["alpha"] = max(0.0, s["alpha"] - dt * 3.0)
            for p in s["particles"]:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
        self._shattered = [s for s in self._shattered if s["alpha"] > 0]

    async def _do_robot_shift(self, battle_ctx, direction_str, steps=1, delta=0):
        """Executa movimentacao fisica via PL_MOV + WAIT_MOV (comandos de descomplexacao).
        Atualiza _tile_offset SOMENTE apos WAIT_MOV confirmar o movimento.
        Se cancelado (runner.clear() no fim do minijogo), reverte _lane para posicao real."""
        self._is_shifting = True
        success = False
        try:
            from game.champions.robot_base import PL_MOV, WAIT_MOV
            await PL_MOV(battle_ctx, direction_str, steps)
            await WAIT_MOV()
            # Movimento fisico confirmado — atualiza posicao real
            self._tile_offset += delta
            success = True
        finally:
            if not success:
                # Cancelado ou falhou — reverte _lane para a posicao fisica real
                self._lane = self._tile_offset + 1
            self._is_shifting = False


    def _create_note_shatter(self, lane, y, color):
        import math
        x = LANE_X[lane]
        particles = []
        for _ in range(8):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(0.1, 0.3)
            particles.append({
                "x": x, "y": y,
                "vx": spd * math.cos(ang),
                "vy": spd * math.sin(ang),
                "size": random.uniform(6, 14)
            })
        self._shattered.append({"alpha": 1.0, "color": color, "particles": particles})

    def evaluate(self) -> str:
        if self._hits >= 14:
            return "excellent"
        elif self._hits >= 7:
            return "good"
        else:
            return "poor"

    def paint(self, painter, width: int, height: int, scale: float):
        self.draw(painter, width, height, scale)

    def draw(self, painter, width, height, scale: float = 1.0):
        painter.save()

        # Flash de coleta
        if self._screen_flash > 0:
            flash_col = QColor(255, 230, 0, int(self._screen_flash * 110))
            painter.fillRect(0, 0, width, height, flash_col)

        # Posicoes X em pixels das 3 faixas
        lx = [int(width * x) for x in LANE_X]

        lane_labels = ["ESQUERDA", "CENTRO", "DIREITA"]
        lane_colors = [QColor(255, 100, 220), QColor(0, 240, 255), QColor(255, 220, 0)]

        # Linhas guia verticais
        pen_track = QPen(QColor(0, 240, 255, 55), 2, Qt.DashLine)
        painter.setPen(pen_track)
        for x in lx:
            painter.drawLine(x, int(height * 0.12), x, int(height * 0.88))

        # Rotulos das faixas no topo
        font_label = QFont("Outfit", max(9, int(11 * scale)), QFont.Bold)
        painter.setFont(font_label)
        for i, x in enumerate(lx):
            painter.setPen(QPen(lane_colors[i]))
            painter.drawText(QRectF(x - 55, int(height * 0.03), 110, 24), Qt.AlignCenter, lane_labels[i])

        # Zonas de coleta (alvos)
        target_y = int(height * 0.80)
        target_r = int(30 * scale)

        for i, x in enumerate(lx):
            if i == self._lane:
                painter.setPen(QPen(lane_colors[i], 3))
                painter.setBrush(QBrush(QColor(lane_colors[i].red(), lane_colors[i].green(), lane_colors[i].blue(), 130)))
                painter.drawEllipse(QPointF(x, target_y), target_r + 8, target_r + 8)
            else:
                painter.setPen(QPen(QColor(100, 100, 120, 90), 2))
                painter.setBrush(QBrush(QColor(40, 40, 60, 50)))
                painter.drawEllipse(QPointF(x, target_y), target_r, target_r)

        # Marcador do robo na faixa ativa
        font_robot = QFont("Outfit", max(14, int(18 * scale)), QFont.Bold)
        painter.setFont(font_robot)
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.drawText(QRectF(lx[self._lane] - 20, target_y - 20, 40, 40), Qt.AlignCenter, "R")

        # Particulas de notas coletadas
        for s in self._shattered:
            alpha_b = int(s["alpha"] * 255)
            c = s["color"]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), alpha_b)))
            for p in s["particles"]:
                px = p["x"] * width
                py = p["y"] * height
                sz = p["size"]
                painter.drawEllipse(QPointF(px, py), sz, sz)

        # Notas caindo
        font_note = QFont("Outfit", max(20, int(28 * scale)), QFont.Bold)
        painter.setFont(font_note)
        for n in self._notes:
            nx = lx[n["lane"]]
            ny = int(n["y"] * height)
            painter.save()
            painter.setPen(QPen(n["color"]))
            painter.drawText(QRectF(nx - 28, ny - 28, 56, 56), Qt.AlignCenter, n["symbol"])
            painter.restore()

        # HUD — notas e faixa atual
        font_score = QFont("Outfit", max(14, int(17 * scale)), QFont.Bold)
        painter.setFont(font_score)
        painter.setPen(QPen(QColor(0, 240, 255), 2))
        lane_name = lane_labels[self._lane]
        painter.drawText(QRectF(20, 20, 420, 36), Qt.AlignLeft, f"NOTAS: {self._hits}   |  FAIXA: {lane_name}")

        painter.restore()


# ═══════════════════════════════════════════════════════════════════════
# Coreografia 3D pos-minijogo — Notas Musicais (Symphony Wave)
# ═══════════════════════════════════════════════════════════════════════

async def execute_symphony_wave_attack(robot, target, ability, final_damage, camera, ctx):
    from game.champions.robot_base import PL_MOV, PL_TURN, PL_ATTACK, WAIT_MOV

    # 1. Drena e aguarda qualquer movimento físico pendente no PenLinux durante o minijogo
    await WAIT_MOV()

    # 2. Centraliza (retorna ao tile inicial)
    tile_offset = getattr(ctx, "symphony_tile_offset", 0)
    if tile_offset == 1:
        # Estava na direita (+1 / TRAS 1) → avança FRENTE 1 para o tile central
        await PL_MOV(ctx, "FRENTE", 1)
        await WAIT_MOV()
    elif tile_offset == -1:
        # Estava na esquerda (-1 / FRENTE 1) → recua TRAS 1 para o tile central
        await PL_MOV(ctx, "TRAS", 1)
        await WAIT_MOV()

    # Limpa a variável após centralizar
    if hasattr(ctx, "symphony_tile_offset"):
        ctx.symphony_tile_offset = 0

    # 3. Vira 90° (ficando de costas para o boss)
    await PL_TURN(ctx, "DIREITA")
    await WAIT_MOV()

    # 4. Anda 2 tiles para trás (avançando em direção ao boss)
    await PL_MOV(ctx, "TRAS", 2)
    await WAIT_MOV()

    # 5. Gira 180° (ficando de frente para o boss)
    await PL_TURN(ctx, "TRAS")
    await WAIT_MOV()

    # 6. Aplica o dano do ataque ao boss com tremor de câmera
    if camera:
        camera.shake(0.35, duration=1.5)
    if final_damage > 0:
        await PL_ATTACK(ctx, final_damage)
        await WAIT_MOV()

    # 7. Anda 2 tiles para trás de novo (retornando à posição original)
    await PL_MOV(ctx, "TRAS", 2)
    await WAIT_MOV()

    # 8. Restaura a visão normal de câmera de batalha se necessário
    if camera and hasattr(camera, "reset_to_battle_view"):
        camera.reset_to_battle_view()

    return True






