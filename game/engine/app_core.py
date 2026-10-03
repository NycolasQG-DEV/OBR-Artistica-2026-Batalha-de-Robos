# engine/app_core.py — classe ShowBase principal (RobotArena3D) e gerenciamento de ciclo de vida
import sys
import os
import time
import threading

from direct.showbase.ShowBase import ShowBase
from direct.gui import DirectGuiGlobals as DGG
from direct.task import Task
from panda3d.core import (
    Point3, LColor, GeomNode, AntialiasAttrib, CullFaceAttrib, Texture
)

from settings import (
    GRID_ROWS, GRID_COLS, C_BG, STATE_SELECT_ROBOT, STATE_PLAYER_TURN,
    STATE_IA_TURN, STATE_MINIGAME, STATE_GAME_OVER, ROBOT_OPTIONS,
    PLAYER_TURN_TIMEOUT, MINIGAME_DURATION, C_GREEN, C_PURPLE, C_RED, C_YELLOW, C_GRAY, C_ORANGE,
    STATE_ATTACK_MINIGAME, STATE_TIMEOUT
)
from game.combat.battle_logic import BattleLogic
from game.config.ui import BASE_DESIGN_WIDTH, BASE_DESIGN_HEIGHT

from game.combat.battle_logic import wait_seconds
from engine.camera.camera_controller import CameraController
from engine.render.geometry import lc, grid_to_world
from engine.render.sky import create_sky_sphere
from engine.render.tile_node import TileNode
from engine.render.robot_node import RobotNode

from ui.hud import QtHUDIntegration

# Modularized game setup, loops, postprocessing and factories
from engine.render.scene_setup import setup_lights, update_skybox
from engine.render.postprocess import setup_dither_postprocess
from engine.render.effects_factory import create_floating, create_particles, create_powerup_particles
from engine.game_loop import game_loop, sync_robot_nodes, update_tile_highlights


game_instance = None


class RobotArena3D(ShowBase):
    def __init__(self, parent_hwnd=None, win_size=None):
        global game_instance
        game_instance = self
        from panda3d.core import loadPrcFileData
        # ── Performance configs ────────────────────────────────────────
        loadPrcFileData("", "sync-video false")
        loadPrcFileData("", "clock-mode limited")
        loadPrcFileData("", "clock-frame-rate 60")
        loadPrcFileData("", "interpolate-frames 1")
        loadPrcFileData("", "textures-power-2 none")
        if parent_hwnd is not None:
            loadPrcFileData("", f"parent-window-handle {parent_hwnd}")
            loadPrcFileData("", "undecorated true")
            loadPrcFileData("", "win-origin 0 0")
            if win_size:
                loadPrcFileData("", f"win-size {win_size[0]} {win_size[1]}")
            else:
                loadPrcFileData("", f"win-size {int(BASE_DESIGN_WIDTH)} {int(BASE_DESIGN_HEIGHT)}")
            
        super().__init__()

        self.disableMouse()
        self.setBackgroundColor(lc(*C_BG))
        self.render.setAntialias(AntialiasAttrib.MAuto)

        # ── Skybox ────────────────────────────────────────────────────
        sky_geom = create_sky_sphere(radius=1.0, segments=32, rings=16)
        sky_geom_node = GeomNode("sky_sphere")
        sky_geom_node.addGeom(sky_geom)
        self.skybox = self.render.attachNewNode(sky_geom_node)
        
        if self.skybox and not self.skybox.isEmpty():
            self.skybox.setScale(500, 500, 500)
            self.skybox.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullNone))
            self.skybox.setDepthWrite(False)
            self.skybox.setDepthTest(False)
            self.skybox.setLightOff()
            self.skybox.setBin("background", 0)
            self.skybox.setColor(LColor(1, 1, 1, 1))
            self.skybox.setMaterialOff(1)
            self.skybox.setShaderOff(1)
            
            sky_tex_path = "assets/textures/skybox.png"
            if os.path.exists(sky_tex_path):
                sky_tex = self.loader.loadTexture(sky_tex_path)
                if sky_tex:
                    sky_tex.setMinfilter(Texture.FTLinearMipmapLinear)
                    sky_tex.setMagfilter(Texture.FTLinear)
                    self.skybox.setTexture(sky_tex, 1)
                    sky_tex.setWrapU(Texture.WMRepeat)
                    sky_tex.setWrapV(Texture.WMClamp)
            else:
                print(f"[RobotArena3D] Textura do Skybox nao encontrada em {sky_tex_path}")
            
            self.taskMgr.add(self._update_skybox, "UpdateSkyboxTask")

        # ── Iluminação ────────────────────────────────────────────────
        setup_lights(self)

        # ── Câmera ────────────────────────────────────────────────────
        self.cam_ctrl = CameraController(self.camera, self)
        self.cam_ctrl.update(0)

        # ── Pós-Processamento Dither PSX ──────────────────────────────
        setup_dither_postprocess(self)

        # ── Great Intelligence (Elemento Cinematográfico de Fundo) ─────
        from engine.render.great_intelligence import GreatIntelligence
        self.great_intelligence = GreatIntelligence(self)

        # ── Grid de tiles ─────────────────────────────────────────────
        self._tiles: list[list[TileNode]] = []
        for row in range(GRID_ROWS):
            row_tiles = []
            for col in range(GRID_COLS):
                row_tiles.append(TileNode(self.render, self.loader, col, row))
            self._tiles.append(row_tiles)

        # ── CV Input ──────────────────────────────────────────────────
        self.cv_input = None
        self._finger_pos_norm = None
        self._input_mode = "mouse"
        self._last_mouse_pos = (0.5, 0.5)
        self._last_cv_pos = (0.5, 0.5)
        self._webcam_mode = "normal"
        self._mouse_pressed = False

        def _init_cv():
            import os
            import sys
            try:
                import cv2
                cam_idx = 0
                config_file = "camera_choice.txt"
                try:
                    from settings import CAMERA_INDEX
                    if CAMERA_INDEX is not None:
                        cam_idx = CAMERA_INDEX
                        print(f"[app.py] Using camera index from settings: {cam_idx}")
                    elif os.path.exists(config_file):
                        with open(config_file, "r") as f:
                            cam_idx = int(f.read().strip())
                        print(f"[app.py] Loaded selected camera index: {cam_idx}")
                    else:
                        print(f"[app.py] Camera choice file '{config_file}' not found. Falling back to default camera (0).")
                except Exception as e:
                    print(f"[app.py] Error checking camera index settings/file: {e}")
                
                if os.path.exists(config_file):
                    try:
                        os.remove(config_file)
                        print(f"[app.py] Camera choice temporary file deleted successfully.")
                    except Exception as e:
                        print(f"[app.py] Error deleting camera choice file: {e}")
                
                backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
                cap = None
                for attempt in range(5):
                    print(f"[app.py] Initializing camera index {cam_idx} (Attempt {attempt+1}/5)...")
                    cap = cv2.VideoCapture(cam_idx, backend)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        print(f"[app.py] Camera index {cam_idx} opened successfully.")
                        break
                    else:
                        print(f"[app.py] Camera index {cam_idx} open failed. Retrying in 0.5s...")
                        cap.release()
                        time.sleep(0.5)
                if cap and not cap.isOpened():
                    cap = None
            except Exception as e:
                print(f"[app.py] Failed to initialize camera: {e}")
                cap = None
            
            from engine.input.cv_input import CVInput
            self.cv_input = CVInput(cap)
            print(f"[app.py] CVInput inicializado em background. cap={'OK' if cap else 'None'}")

        # ── Inicializa câmera em thread de background ─────────────────────────
        # A câmera começa a capturar e o HandLandmarker é carregado enquanto
        # a tela de seleção de personagem já está sendo exibida ao usuário.
        # cv_input começa como None e é atribuído assim que a thread termina.
        # O game_loop trata cv_input=None graciosamente (sem crash).
        _cv_thread = threading.Thread(target=_init_cv, name="CVInitThread", daemon=True)
        _cv_thread.start()


        # ── Battle logic ──────────────────────────────────────────────
        self.battle = BattleLogic(
            camera              = self.cam_ctrl,
            create_floating_fn  = self._create_floating,
            create_particles_fn = self._create_particles,
            log_fn              = self._add_log,
        )
        self.battle.app = self
        self.battle.on_state_change = self._on_state_change

        # ── Serial Connection check ───────────────────────────────────
        from game.combat.serial_controller import get_serial_controller
        get_serial_controller()


        # ── Nodes de robôs ────────────────────────────────────────────
        self._robot_nodes: dict[str, RobotNode] = {}

        # ── Partículas e floating texts ───────────────────────────────
        self._particles:     list = []
        self._floating_texts: list = []

        # ── Log ───────────────────────────────────────────────────────
        self._battle_log: list[tuple[str, float]] = [("ROBOT ARENA 3D iniciado", time.time())]

        # ── BGM & ATO 2 / Músicas de Fundo do Jogo ──────────────────────
        self.bgm = None
        self.act2_audio = None
        self._bgm_fade_task = None
        try:
            bgm_path = "assets/sounds/backgroundBattleTheme.mp3"
            if os.path.exists(bgm_path):
                self.bgm = self.loader.loadMusic(bgm_path)
                if self.bgm:
                    self.bgm.setLoop(True)
                    self.bgm.setVolume(0.0)

            # Bypass Panda3D AudioManager usando QMediaPlayer do PySide6 para o ATO2
            # Isso garante que ele não diminua o volume da BGM e toque o arquivo grande perfeitamente.
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl
            act2_path_abs = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "ATO2.mp3"))
            if os.path.exists(act2_path_abs):
                self.act2_player = QMediaPlayer()
                self.act2_output = QAudioOutput()
                self.act2_output.setVolume(1.4)
                self.act2_player.setAudioOutput(self.act2_output)
                self.act2_player.setSource(QUrl.fromLocalFile(act2_path_abs))
                self.act2_audio = None # Fallback compat
                print(f"[app_core.py] ATO2 carregado via QMediaPlayer (Isolado): {act2_path_abs}")
            else:
                self.act2_player = None
                self.act2_audio = None
        except Exception as e:
            print(f"[app_core.py] Erro ao carregar audios de fundo: {e}")

        # ── SFX / Sons ────────────────────────────────────────────────
        self.snd_hover  = self.loader.loadSfx("assets/sounds/hover.wav")
        self.snd_select = self.loader.loadSfx("assets/sounds/select.wav")
        self.snd_hit    = self.loader.loadSfx("assets/sounds/hit.wav")
        self.snd_dodge  = self.loader.loadSfx("assets/sounds/dodge.wav")
        self.snd_alert  = self.loader.loadSfx("assets/sounds/alert.wav")

        # ── HUD ───────────────────────────────────────────────────────
        self.hud = QtHUDIntegration(self, self.battle)

        # ── Estado de input ───────────────────────────────────────────
        self._action_hover:  str | None = None
        self._hover_timer:   float      = 0.0
        self._turn_start:    float      = 0.0
        self._prev_state:    str        = STATE_SELECT_ROBOT

        # Timeout do turno
        self._timed_out = False

        # ── Attack Minigames ──
        self.active_attack_minigame = None
        self.selected_attack_action = None

        # ── Mouse/Keyboard click handlers ─────────────────────────────
        self.accept("r",      self._reset)
        self.accept("R",      self._reset)
        self.accept("escape", self._on_escape)
        self.accept("mouse1", self._on_mouse1_down)
        self.accept("mouse1-up", self._on_mouse1_up)

        # ── Task principal ────────────────────────────────────────────
        self.taskMgr.add(self._game_loop, "game_loop")

        # Tamanho da janela
        if hasattr(self, "win") and self.win is not None:
            if hasattr(self.win, "getProperties"):
                props = self.win.getProperties()
                self._screen_w = props.getXSize()
                self._screen_h = props.getYSize()
            else:
                self._screen_w = self.win.getXSize()
                self._screen_h = self.win.getYSize()
        else:
            self._screen_w = int(BASE_DESIGN_WIDTH)
            self._screen_h = int(BASE_DESIGN_HEIGHT)

    # ── Modular forward helpers ───────────────────────────────────────

    def _update_skybox(self, task):
        return update_skybox(self, task)

    def _game_loop(self, task):
        return game_loop(self, task)

    def _sync_robot_nodes(self):
        sync_robot_nodes(self)

    def _update_tile_highlights(self):
        update_tile_highlights(self)

    def _create_floating(self, tx, ty, text, color, size=1.0):
        create_floating(self, tx, ty, text, color, size)

    def _create_particles(self, tx, ty, color, count=12, speed=1.0):
        create_particles(self, tx, ty, color, count, speed)

    def _create_powerup_particles(self, tx, ty, color, count=15):
        create_powerup_particles(self, tx, ty, color, count)

    # ── State transitions and callbacks ───────────────────────────────

    def _on_state_change(self, new_state: str):
        if new_state == STATE_SELECT_ROBOT:
            pass

        elif new_state == "intro":
            self.screens.show("battle")
            self.hud.clear_action_buttons()
            if hasattr(self, "_tiles"):
                for row in self._tiles:
                    for tile in row:
                        if hasattr(tile, "node"):
                            tile.node.show()

        elif new_state == STATE_PLAYER_TURN:
            self.screens.show("battle")
            
            # Se o tempo acabou ANTES de mostrar a alavanca (novo round)
            if hasattr(self.battle, "match_time_remaining") and self.battle.match_time_remaining <= 0.0:
                print("[TIMEOUT] Tempo esgotado no início do round! Ativando sequência imediatamente.")
                self.battle.request_timeout()
                return

            if not self.battle.is_executing_action and self.battle.action_complete_time == 0:
                self._turn_start = time.time()
                self._timed_out  = False
                self.hud.show_banner("SEU TURNO!", C_GREEN)
                if self.battle.player_robot:
                    self.hud.build_action_buttons(
                        self.battle.player_robot, self._on_action_selected)
                self.cam_ctrl.enter_action_selection_mode()
                if hasattr(self, "qt_win") and self.qt_win:
                    self.qt_win.enter_selection_hud_mode()

        elif new_state == STATE_IA_TURN:
            self.screens.show("battle")
            self.hud.clear_action_buttons()
            self.hud.show_banner("TURNO DA IA", C_PURPLE)
            self._turn_start = 0.0
            if not self.battle.is_executing_action:
                self.cam_ctrl.cinematic_zoom_in()

        elif new_state == STATE_MINIGAME:
            self.screens.show("battle")
            self._turn_start = 0.0
            self._timed_out  = False
            self.hud.clear_action_buttons()
            attack_dir = getattr(self.battle, "minigame_attack_dir", "left")
            self.hud.build_minigame_dodge(self._on_dodge_selected, attack_dir)
            self.hud.show_banner("DESVIE!", C_RED)
            if not (self.battle.player_robot and self.battle.player_robot.name_code.lower() == "penlinux"):
                self.cam_ctrl.enter_minigame_mode()
            if self.battle.player_robot:
                self.battle.player_robot.target_h = self.battle.player_robot.heading_to_boss
            if hasattr(self, "qt_win") and self.qt_win:
                self.qt_win.enter_minigame_hud_mode(attack_dir)

        elif new_state == STATE_ATTACK_MINIGAME:
            self.screens.show("battle")
            self.hud.clear_action_buttons()
            self._turn_start = 0.0
            self._timed_out  = False

        elif new_state in (STATE_GAME_OVER, STATE_TIMEOUT):
            self.screens.show("battle")
            self.hud.clear_action_buttons()
            self._turn_start = 0.0
            self._timed_out  = False
            if hasattr(self, "qt_win") and self.qt_win:
                if hasattr(self.qt_win, "exit_selection_hud_mode"):
                    self.qt_win.exit_selection_hud_mode()
                if hasattr(self.qt_win, "exit_minigame_hud_mode"):
                    self.qt_win.exit_minigame_hud_mode()
                if hasattr(self.qt_win, "exit_attack_minigame_hud_mode"):
                    self.qt_win.exit_attack_minigame_hud_mode()
            
            # Inicia a mesma sequência cinematográfica assíncrona da Great Intelligence (Vitória, Derrota, Empate ou Timeout)
            from game.minigames.timeout_sequence import execute_timeout_sequence
            self._timeout_sequence_started = True
            self.battle._runner.clear()
            self.battle._runner.start(execute_timeout_sequence(self, self.cam_ctrl, self.battle))

    def _show_select_screen(self):
        if self.qt_win:
            self.qt_win.show_select_screen()

    def setup_screens(self):
        from engine.screen_manager import ScreenManager
        from game.screens.game_over_screen import GameOverScreen

        self.screens = ScreenManager()
        self.screens.register("battle", self.qt_win.panda_container)
        self.screens.register("game_over", GameOverScreen(self))
        self.screens.show("battle")
        
        self._on_state_change(self.battle.state)

    def start_bgm_fade_in(self, target_volume=0.2, fade_duration=2.0):
        # O usuário solicitou uma execução "caótica" e direta, sem fades.
        # Definimos o volume absoluto de ambas as faixas imediatamente.
        if self._bgm_fade_task:
            try:
                self.taskMgr.remove(self._bgm_fade_task)
            except Exception:
                pass
            
        if self.bgm:
            self.bgm.setVolume(target_volume)
            self.bgm.play()

        # Toca ATO2 via player nativo (sem influência ou perdas pelo Panda3D)
        if hasattr(self, "act2_player") and self.act2_player:
            self.act2_output.setVolume(1.4)  # Ampliado em 2x (0.7 -> 1.4)
            self.act2_player.play()
        elif hasattr(self, "act2_audio") and self.act2_audio:
            self.act2_audio.setVolume(1.4)
            self.act2_audio.play()

    def duck_bgm_for_sound(self, sound, duck_volume=0.08, normal_volume=1.2, fade_time=0.4):
        # O usuário solicitou que os canais toquem de forma independente sem redução de volume (ducking).
        # A música de fundo e o ATO2.mp3 continuarão tocando normalmente.
        if not sound:
            return
        
        sound.setVolume(1.0)
        sound.play()

    def _on_robot_selected(self, opt: dict):
        self.battle.select_player_robot(opt["color"], opt["name"])
        self.cam_ctrl.set_center(0, 0)
        self._sync_robot_nodes()
        self.battle._runner.start(self._seq_challenge_intro())

    async def _seq_challenge_intro(self):
        # ── PRÉ-COMPUTAÇÃO E AQUECIMENTO (Garante 0 engasgos durante a cena) ──
        self.hud._p_bg.hide()
        self.hud._boss_bg.hide()
        self.hud._portrait_bg.hide()
        if hasattr(self, "dr_pip") and self.dr_pip:
            self.dr_pip.setActive(False)

        # Ativa as barras cinemáticas pretas durante a intro
        self.hud.show_cinematic_bars(True)

        pr = self.battle.player_robot
        ia = self.battle.ia_robot
        if not pr or not ia:
            return

        # Garante que os nós 3D de ambos os robôs estão visíveis, compilados nos shaders da GPU e renderizados
        self._sync_robot_nodes()
        self.graphicsEngine.renderFrame()
        self.graphicsEngine.renderFrame()

        p_pos = grid_to_world(pr.v_tx, pr.v_ty)
        b_pos = grid_to_world(ia.v_tx, ia.v_ty)

        def get_robot_color_hex(name_code):
            return "#ff9900" if "dino" in name_code.lower() else "#55b5ff"

        def format_robot_display_name(name_code):
            return "DINO-BYTE" if "dino" in name_code.lower() else "PENLINUX"

        p_color = get_robot_color_hex(pr.name_code)
        b_color = get_robot_color_hex(ia.name_code)

        p_name = format_robot_display_name(pr.name_code)
        b_name = format_robot_display_name(ia.name_code)

        # ── DISPARO DA MÚSICA DE FUNDO COM FADE-IN (Sincronizado após tudo computado) ──
        self.start_bgm_fade_in(target_volume=0.6, fade_duration=1.5)

        # Helper para aguardar segundos cravados pelo relógio do sistema (independente de variação de FPS)
        async def wait_real_seconds(sec_duration):
            t_end = time.time() + sec_duration
            from game.combat.battle_logic import _tick
            while time.time() < t_end:
                await _tick()

        # ── 1. VISÃO LATERALIZADA AFASTADA E APROXIMAÇÃO LENTA (2.0s) ──
        mid_pos = (p_pos + b_pos) * 0.5
        self.cam_ctrl.set_camera_speed("slow")
        self.cam_ctrl._target_center = Point3(mid_pos.getX(), mid_pos.getY(), 0.9)
        self.cam_ctrl._center = Point3(mid_pos.getX(), mid_pos.getY(), 0.9)
        self.cam_ctrl._target_heading = 90.0
        self.cam_ctrl._heading = 90.0
        self.cam_ctrl._target_pitch = -12.0
        self.cam_ctrl._pitch = -12.0
        self.cam_ctrl._dist = 20.0
        self.cam_ctrl._target_dist = 14.0
        await wait_real_seconds(1.8)

        async def play_cinematic_character_focus(name, color_hex, pos, is_player=True):
            # Transição suave para enquadramento cinemático (distância 8.5 unidades = sem entrar no modelo)
            self.cam_ctrl.set_camera_speed("normal")
            self.cam_ctrl._target_center = Point3(pos.getX(), pos.getY(), 1.0)
            self.cam_ctrl._target_dist = 8.5
            self.cam_ctrl._target_pitch = -10.0
            
            # Giro orbital fluido em torno do robô
            start_h = 15.0 if is_player else -15.0
            end_h   = 45.0 if is_player else -45.0
            self.cam_ctrl._target_heading = start_h

            await wait_real_seconds(0.4)

            # Inicia movimento orbital lento
            self.cam_ctrl.set_camera_speed("slow")
            self.cam_ctrl._target_heading = end_h

            # Destaque do nome com pulso suave de câmera
            for i in range(2):
                self.cam_ctrl.trigger_camera_pulse(1.2)
                self.hud.show_banner(name, color_hex, duration=0.15, font_size_mult=3.2, pos_y_ratio=0.45)
                await wait_real_seconds(0.15)
                if hasattr(self.qt_win, "banner_overlay"):
                    self.qt_win.banner_overlay.hide()
                await wait_real_seconds(0.10)

            # Nome permanece visível durante a órbita suave
            self.hud.show_banner(name, color_hex, duration=1.5, font_size_mult=3.2, pos_y_ratio=0.45)
            await wait_real_seconds(1.5)

        # ── 2. APRESENTAÇÃO DO PLAYER (2.3s) ──
        await play_cinematic_character_focus(p_name, p_color, p_pos, is_player=True)

        # ── 3. APRESENTAÇÃO DO BOSS / IA (2.3s) ──
        await play_cinematic_character_focus(b_name, b_color, b_pos, is_player=False)

        # ── 4. RETORNO À VISÃO LATERALIZADA & INÍCIO DO COMBATE (1.8s) ──
        self.cam_ctrl.trigger_camera_pulse(1.0)
        self.cam_ctrl.set_camera_speed("slow")
        self.cam_ctrl._target_center = Point3(mid_pos.getX(), mid_pos.getY(), 0.8)
        self.cam_ctrl._target_heading = 90.0
        self.cam_ctrl._target_pitch = -12.0
        self.cam_ctrl._target_dist = 15.0

        self.hud.show_banner("COMBATE INICIADO!", "#ffcc00", duration=2.0, font_size_mult=1.4, pos_y_ratio=0.30)
        await wait_real_seconds(2.0)

        # Restaura HUD normal, esconde barras cinemáticas e inicia o jogo
        self.hud.show_cinematic_bars(False)
        self.hud._p_bg.show()
        self.hud._boss_bg.show()
        self.hud._portrait_bg.show()
        if hasattr(self, "dr_pip") and self.dr_pip:
            self.dr_pip.setActive(True)

        self.cam_ctrl.set_camera_speed("normal")
        self.cam_ctrl.reset_to_battle_view()
        self.battle.state = STATE_PLAYER_TURN
        self._on_state_change(STATE_PLAYER_TURN)
        self.battle.log(f"--- TURNO {self.battle.turn_number} ---")

    def _on_action_selected(self, action: str):
        pr = self.battle.player_robot
        if not pr or self.battle.state != STATE_PLAYER_TURN:
            return
        if self.battle.is_executing_action or self.battle.action_complete_time > 0:
            return



        self.hud.clear_action_buttons()
        
        if hasattr(self, "qt_win") and self.qt_win:
            if action != "atk1":
                self.qt_win.exit_selection_hud_mode()

        if action.startswith("atk"):
            if pr and hasattr(pr, "record_attack_used"):
                pr.record_attack_used(action)
            idx = int(action[-1])
            ability = pr.abilities[idx]
            if ability.triggers_minigame:
                self._turn_start = 0.0
                self.selected_attack_action = action
                
                from game.minigames import get_minigame_for_attack
                self.active_attack_minigame = get_minigame_for_attack(action, pr.name_code)
                
                # Garante parada dos motores durante a interface do minijogo
                from game.combat.serial_controller import get_serial_controller
                get_serial_controller().send_command_realtime(pr, "STOP", 0)
                
                # Se for DanceNight (PenLinux), executa a movimentação primeiro antes de abrir a interface
                if self.active_attack_minigame.__class__.__name__ == "DanceNightMinigame":
                    self.battle.is_executing_action = True
                    self.battle._runner.clear()
                    self.battle._runner.start(self._seq_pre_minigame_dance_night(action))
                    return
                elif self.active_attack_minigame.__class__.__name__ == "FrostBarrierMinigame":
                    self.battle.is_executing_action = True
                    self.battle._runner.clear()
                    self.battle._runner.start(self._seq_pre_minigame_frost_barrier(action))
                    return
                elif self.active_attack_minigame.__class__.__name__ == "SymphonyWaveMinigame":
                    self.battle.is_executing_action = True
                    self.battle._runner.clear()
                    self.battle._runner.start(self._seq_pre_minigame_symphony_wave(action))
                    return

                self.battle.state = STATE_ATTACK_MINIGAME
                if self.active_attack_minigame.__class__.__name__ == "MeteorStompMinigame":
                    if hasattr(self, "cam_ctrl") and self.cam_ctrl:
                        self.cam_ctrl.enter_meteor_stomp_mode(pr)
                    if hasattr(self, "qt_win") and self.qt_win:
                        self.qt_win.enter_attack_minigame_hud_mode(self.active_attack_minigame)
                else:
                    if hasattr(self, "cam_ctrl") and self.cam_ctrl:
                        if pr.name_code.lower() == "penlinux":
                            pass
                        elif self.active_attack_minigame.__class__.__name__ in ["DanceNightMinigame", "BlizzardSlashMinigame"]:
                            self.cam_ctrl.enter_dance_night_mode()
                        else:
                            self.cam_ctrl.enter_minigame_mode()

                    if hasattr(self, "qt_win") and self.qt_win:
                        self.qt_win.enter_attack_minigame_hud_mode(self.active_attack_minigame)
            else:
                self.battle.execute_player_action(action, "good")
                self._turn_start = 0.0

    async def _seq_pre_minigame_dance_night(self, action: str):
        from game.minigames.dance_night import player_attack_sequence_dance_night
        pr = self.battle.player_robot
        ia = self.battle.ia_robot
        if not pr or not ia:
            return
        idx = int(action[-1])
        ability = pr.abilities[idx]

        # 1. Executa movimentação 3D + close-in de câmera primeiro
        await player_attack_sequence_dance_night(pr, ia, ability, 0, self.cam_ctrl, self.battle)

        # 2. Abre a interface e overlay do minijogo de dança após o movimento
        self.battle.is_executing_action = False
        self.battle.state = STATE_ATTACK_MINIGAME
        if hasattr(self, "qt_win") and self.qt_win:
            self.qt_win.enter_attack_minigame_hud_mode(self.active_attack_minigame)

    async def _seq_pre_minigame_frost_barrier(self, action: str):
        from game.champions.robot_base import PL_MOV, DB_MOV, WAIT_MOV
        pr = self.battle.player_robot
        ia = self.battle.ia_robot
        if not pr or not ia:
            return

        # 1. Ambos os robôs (PenLinux e DinoByte) andam 1 tile para frente
        await PL_MOV(self.battle, "FRENTE", 1)
        await DB_MOV(self.battle, "FRENTE", 1)
        await WAIT_MOV()

        # 2. PenLinux ativa a barreira azul transparente e pulsante em torno dele
        self._create_3d_barrier_node(pr)

        # 3. Transita para o minijogo Escudo de Gelo e exibe o overlay
        self.battle.is_executing_action = False
        self.battle.state = STATE_ATTACK_MINIGAME
        if hasattr(self, "qt_win") and self.qt_win:
            self.qt_win.enter_attack_minigame_hud_mode(self.active_attack_minigame)

    async def _seq_pre_minigame_symphony_wave(self, action: str):
        from game.champions.robot_base import PL_TURN, WAIT_MOV
        pr = self.battle.player_robot
        ia = self.battle.ia_robot
        if not pr or not ia:
            return

        # 1. PenLinux gira 90° para a direita
        await PL_TURN(self.battle, "DIREITA")
        await WAIT_MOV()

        # 2. Transita para o minijogo Notas Musicais e exibe o overlay
        self.battle.is_executing_action = False
        self.battle.state = STATE_ATTACK_MINIGAME
        if hasattr(self, "qt_win") and self.qt_win:
            self.qt_win.enter_attack_minigame_hud_mode(self.active_attack_minigame)

    def _create_3d_barrier_node(self, robot):
        """Cria a barreira esférica 3D transparente e pulsante em torno do robô."""
        import math
        from panda3d.core import TransparencyAttrib, NodePath, CardMaker
        if hasattr(self, "_barrier_node") and self._barrier_node:
            try:
                self._barrier_node.removeNode()
            except Exception:
                pass

        try:
            sphere_model = self.loader.loadModel("models/misc/sphere")
        except Exception:
            cm = CardMaker("barrier_card")
            cm.setFrame(-1.0, 1.0, -1.0, 1.0)
            sphere_model = NodePath(cm.generate())

        if hasattr(robot, "node") and robot.node:
            sphere_model.reparentTo(robot.node)
        else:
            sphere_model.reparentTo(self.render)

        sphere_model.setPos(0, 0, 0.6)
        sphere_model.setScale(2.2)
        sphere_model.setColor(0.1, 0.65, 1.0, 0.45)
        sphere_model.setTransparency(TransparencyAttrib.MAlpha)

        self._barrier_node = sphere_model
        self._barrier_start_time = time.time()
        self._barrier_exploding = False

        def pulse_task(task):
            if not hasattr(self, "_barrier_node") or not self._barrier_node or self._barrier_node.isEmpty():
                return Task.done
            if getattr(self, "_barrier_exploding", False):
                return Task.cont
            t = time.time() - self._barrier_start_time
            s = 2.2 + 0.35 * math.sin(t * 5.0)
            self._barrier_node.setScale(s)
            return Task.cont

        self.taskMgr.add(pulse_task, "_barrier_pulse_task")

    async def _trigger_3d_barrier_explosion(self, on_explode_callback=None):
        """Animação de carregamento pulsante do escudo e explosão cobrindo a arena inteira."""
        import math
        from panda3d.core import TransparencyAttrib
        if not hasattr(self, "_barrier_node") or not self._barrier_node or self._barrier_node.isEmpty():
            if on_explode_callback:
                await on_explode_callback()
            return

        self._barrier_exploding = True
        node = self._barrier_node

        # 1. Animaçãozinha de carregamento do escudo (vibração e brilho crescente por ~1.2s)
        for i in range(25):
            t = i / 25.0
            s = 2.2 + 0.45 * math.sin(i * 1.8) + t * 0.8  # Vibração rápida e escala inflando
            alpha = 0.45 + t * 0.4                       # Brilho azul intenso
            node.setScale(s)
            node.setColor(0.2 + t * 0.3, 0.75 + t * 0.25, 1.0, alpha)
            await wait_seconds(0.04)

        # 2. MOMENTO DA EXPLOSÃO: Executa o callback (Dano + Camerashake de 2s)
        if on_explode_callback:
            await on_explode_callback()

        # 3. Expansão rápida cobrindo toda a arena + partículas de explosão 3D
        pr = self.battle.player_robot
        if pr:
            self._create_particles(pr.v_tx, pr.v_ty, (0.1, 0.85, 1.0, 1.0), count=40, speed=10.0)

        for i in range(15):
            t = (i + 1) / 15.0
            s = 3.2 + t * 35.0  # expande até 38.0 (cobertura total da arena)
            alpha = max(0.0, 0.85 * (1.0 - t))
            node.setScale(s)
            node.setColor(0.3, 0.9, 1.0, alpha)
            await wait_seconds(0.02)

        # 4. Limpeza do nó
        try:
            node.removeNode()
        except Exception:
            pass
        self._barrier_node = None
        self._barrier_exploding = False

    def _on_dodge_selected(self, direction: str):
        if self.battle.state != STATE_MINIGAME:
            return
        self.hud.clear_action_buttons()
        self.battle.resolve_minigame(direction)

    def _on_mouse1_down(self):
        self._mouse_pressed = True
        if hasattr(self, "qt_win") and self.qt_win:
            self.qt_win.raise_overlays()
        self._on_click_confirmed()

    def _on_mouse1_up(self):
        self._mouse_pressed = False

    def _on_click_confirmed(self):
        if self.battle.state in (STATE_PLAYER_TURN, STATE_MINIGAME, STATE_SELECT_ROBOT):
            active_btn = self.hud.get_active_button()
            if active_btn and active_btn['state'] != DGG.DISABLED:
                if hasattr(self, "snd_select") and self.snd_select:
                    self.snd_select.play()
                
                action = getattr(active_btn, "select_action", None)
                if action:
                    if self.battle.state == STATE_PLAYER_TURN:
                        self._on_action_selected(action)
                    elif self.battle.state == STATE_MINIGAME:
                        self._on_dodge_selected(action)
                elif active_btn['command']:
                    active_btn['command'](*active_btn['extraArgs'])

    def _on_escape(self):
        if hasattr(self, "qt_win") and self.qt_win:
            self.qt_win.close()
        else:
            self.destroy()
            sys.exit(0)

    def _reset(self):
        for node in self._robot_nodes.values():
            node.destroy()
        self._robot_nodes.clear()
        self._particles.clear()
        self._floating_texts.clear()

        self.battle.reset()
        self.cam_ctrl.set_center(0, 0)
        self.cam_ctrl.enter_select_mode()

        self._turn_start  = 0.0
        self._timed_out   = False
        self._action_hover = None
        self._hover_timer  = 0.0
        self._prev_state   = STATE_SELECT_ROBOT

        self.active_attack_minigame = None
        self.selected_attack_action = None
        if hasattr(self, "qt_win") and self.qt_win:
            self.qt_win.exit_attack_minigame_hud_mode()

        self._battle_log = [("JOGO REINICIADO", time.time())]
        self._on_state_change(STATE_SELECT_ROBOT)
        self._show_select_screen()

    def _add_log(self, msg: str):
        self._battle_log.append((msg, time.time()))
        if len(self._battle_log) > 40:
            self._battle_log.pop(0)

    def destroy(self):
        if hasattr(self, "cv_input") and self.cv_input:
            self.cv_input.release()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
