# engine/game_loop.py — processamento de frame principal e sincronização física de robôs/ladrilhos
import math
import time
import traceback
from direct.task import Task
from panda3d.core import Vec2
from settings import (
    STATE_SELECT_ROBOT, STATE_PLAYER_TURN, STATE_IA_TURN, STATE_MINIGAME,
    STATE_ATTACK_MINIGAME, STATE_TIMEOUT, STATE_GAME_OVER, PLAYER_TURN_TIMEOUT, C_ORANGE
)
from engine.render.geometry import grid_to_world
from engine.camera.camera_controller import CameraController

def game_loop(app, task):
    dt = app.taskMgr.globalClock.getDt()
    dt = min(dt, 0.05)

    # CV Input
    cv_pos = None
    cv_hand_closed = False
    is_stomp_active = False
    is_symphony_active = False
    if app.cv_input is not None:
        is_tail_active = getattr(app.battle, "tail_minigame_active", False)
        is_stomp_active = (app.battle.state == STATE_ATTACK_MINIGAME and 
                           app.active_attack_minigame and 
                           app.active_attack_minigame.__class__.__name__ == "MeteorStompMinigame")
        is_symphony_active = (app.battle.state == STATE_ATTACK_MINIGAME and 
                             app.active_attack_minigame and 
                             app.active_attack_minigame.__class__.__name__ == "SymphonyWaveMinigame")
        use_head_tracking = (app.battle.state == STATE_MINIGAME or is_tail_active or is_stomp_active or is_symphony_active)
        app.cv_input.face_detection_enabled = use_head_tracking

        if use_head_tracking:
            with app.cv_input._lock:
                face_x = app.cv_input.face_x
                face_y = app.cv_input.face_y
            if face_x is not None and face_y is not None:
                cv_pos = (face_x, face_y)
        else:
            cv_pos, cv_hand_closed = app.cv_input.update()

    # Mouse Input
    mouse_pos = None
    if app.mouseWatcherNode.hasMouse():
        mx = app.mouseWatcherNode.getMouseX()
        my = app.mouseWatcherNode.getMouseY()
        nx = (mx + 1.0) / 2.0
        ny = (1.0 - my) / 2.0
        mouse_pos = (nx, ny)

    # Detect active input mode
    mouse_moved = False
    if mouse_pos is not None:
        dx = mouse_pos[0] - app._last_mouse_pos[0]
        dy = mouse_pos[1] - app._last_mouse_pos[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > 0.005:
            app._input_mode = "mouse"
            app._last_mouse_pos = mouse_pos
            mouse_moved = True

    if cv_pos is not None:
        if app.battle.state == STATE_MINIGAME or is_stomp_active or is_symphony_active:
            if not mouse_moved and app._input_mode != "mouse":
                app._input_mode = "cv"
            app._last_cv_pos = cv_pos
        else:
            dx = cv_pos[0] - app._last_cv_pos[0]
            dy = cv_pos[1] - app._last_cv_pos[1]
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 0.015 or cv_hand_closed:
                app._input_mode = "cv"
                app._last_cv_pos = cv_pos

    # Assign finger pos and hand closed states
    if app._input_mode == "cv":
        if cv_pos is not None and cv_pos[0] is not None and cv_pos[1] is not None:
            app._finger_pos_norm = cv_pos
        else:
            app._finger_pos_norm = None
        hand_closed = cv_hand_closed if app._finger_pos_norm is not None else False
    else:
        if mouse_moved or app._finger_pos_norm is None:
            app._finger_pos_norm = mouse_pos
        hand_closed = False

    # Camera
    app.cam_ctrl.update(dt)

    # Battle logic
    try:
        app.battle.update(dt)
    except Exception as e:
        print("--- BATTLE UPDATE EXCEPTION ---")
        traceback.print_exc()
        with open("battle_update_crash.txt", "w") as f:
            traceback.print_exc(file=f)
        raise e

    # Update Great Intelligence (Levitação cinematográfica de fundo)
    if hasattr(app, "great_intelligence") and app.great_intelligence:
        app.great_intelligence.update(dt)

    # Update robot nodes
    for key, node in list(app._robot_nodes.items()):
        node.update(dt)

    # Sync nodes
    sync_robot_nodes(app)

    # Resize handler
    if hasattr(app, "win") and app.win is not None:
        props = app.win.getProperties()
        sw = props.getXSize()
        sh = props.getYSize()
        if sw != app._screen_w or sh != app._screen_h:
            app._screen_w = sw
            app._screen_h = sh
            if hasattr(app, "filter_manager") and app.filter_manager:
                try:
                    app.filter_manager.resizeBuffers()
                except Exception as e:
                    print(f"[app.py] Error resizing FilterManager buffers: {e}")
            if hasattr(app, "dither_quad") and app.dither_quad:
                app.dither_quad.setShaderInput("win_size", Vec2(sw, sh))

    # Particles and texts
    app._particles = [p for p in app._particles if p.update(dt)]
    app._floating_texts = [ft for ft in app._floating_texts if ft.update(dt)]

    # Dynamic camera center
    pr = app.battle.player_robot
    ia = app.battle.ia_robot
    if pr and ia:
        if app.cam_ctrl._mode == CameraController.MODE_IDLE:
            wp = grid_to_world(pr.v_tx, pr.v_ty)
            wi = grid_to_world(ia.v_tx, ia.v_ty)
            cx = (wp.getX() + wi.getX()) / 2
            cy = (wp.getY() + wi.getY()) / 2
            app.cam_ctrl.set_center(cx, cy)

    # Highlights (throttled - a cada 3 frames)
    if not hasattr(app, '_tile_frame_counter'):
        app._tile_frame_counter = 0
    app._tile_frame_counter += 1
    if app._tile_frame_counter >= 3:
        app._tile_frame_counter = 0
        update_tile_highlights(app)
        for row in app._tiles:
            for tile in row:
                tile.pulse(dt * 3)

    # Match timer remaining & Game Over / Timeout auto-close
    state = app.battle.state
    if state in (STATE_PLAYER_TURN, STATE_IA_TURN, STATE_MINIGAME, STATE_ATTACK_MINIGAME, STATE_TIMEOUT, STATE_GAME_OVER):
        if state not in (STATE_TIMEOUT, STATE_GAME_OVER):
            app.battle.match_time_remaining = app.battle.match_time_remaining - dt
            
            # Hard-limit de 1:50 (110s) -> O jogo tem 90s, então passa 20s.
            if app.battle.match_time_remaining <= -20.0:
                print("\n[CRITICAL TIMEOUT] Hard-limit absoluto de 1:50 atingido! Fechando o jogo por segurança.\n")
                import sys
                if hasattr(app, "qt_win") and app.qt_win:
                    app.qt_win.close()
                elif hasattr(app, "destroy"):
                    app.destroy()
                sys.exit(0)

            # Fuga de Emergência de 1:40 (100s) -> O jogo tem 90s, então passa 10s.
            if app.battle.match_time_remaining <= -10.0:
                # STRICT REST CHECK: Verifica se os robôs estão se movendo ou fora da base
                robots_busy = False
                if getattr(app.battle, "player_robot", None):
                    pr = app.battle.player_robot
                    if getattr(pr, "is_moving", False): robots_busy = True
                    if abs(pr.v_tx - pr.base_tx) > 0.01 or abs(pr.v_ty - pr.base_ty) > 0.01: robots_busy = True
                if getattr(app.battle, "ia_robot", None):
                    ir = app.battle.ia_robot
                    if getattr(ir, "is_moving", False): robots_busy = True
                    if abs(ir.v_tx - ir.base_tx) > 0.01 or abs(ir.v_ty - ir.base_ty) > 0.01: robots_busy = True
                
                if robots_busy:
                    # Não executa fuga de emergência se os robôs estão se movendo (espera eles terminarem)
                    pass
                elif not getattr(app.battle, "timeout_triggered", False):
                    if not getattr(app.battle, "_emergency_retreat_started", False):
                        app.battle._emergency_retreat_started = True
                        print("[EMERGENCY] Minigame ainda ativo aos 1:40! Cancelando e recuando os robôs.")
                        
                        app.battle.state = STATE_TIMEOUT
                        app.battle.is_executing_action = False
                        
                        if hasattr(app, "active_attack_minigame") and app.active_attack_minigame:
                            app.active_attack_minigame = None
                            
                        if hasattr(app.battle, "_runner") and app.battle._runner:
                            app.battle._runner.clear()
                            
                            async def emergency_retreat_coro():
                                import asyncio
                                tasks = []
                                if getattr(app.battle, "player_robot", None):
                                    tasks.append(app.battle.player_robot.return_to_initial_pose())
                                if getattr(app.battle, "boss_robot", None):
                                    tasks.append(app.battle.boss_robot.return_to_initial_pose())
                                
                                if tasks:
                                    await asyncio.gather(*tasks)
                                
                                print("[EMERGENCY] Fuga concluída! Fechando o jogo IMEDIATAMENTE.")
                                import sys
                                if hasattr(app, "qt_win") and app.qt_win:
                                    app.qt_win.close()
                                elif hasattr(app, "destroy"):
                                    app.destroy()
                                sys.exit(0)
                                
                            app.battle._runner.start(emergency_retreat_coro())

            # Se o tempo acabou (<= 0.0) E estamos aguardando a alavanca (sem fazer nada)
            if app.battle.match_time_remaining <= 0.0:
                if state == STATE_PLAYER_TURN and hasattr(app.battle, "_robots_at_rest") and app.battle._robots_at_rest():
                    if not getattr(app.battle, "timeout_requested", False):
                        print("[TIMEOUT] Tempo esgotado enquanto aguarda alavanca! Ativando sequência.")
                        app.battle.request_timeout()

        # Se o tempo de partida expirou, verifica a cada frame se as ações/transmissões seriais em andamento já foram concluídas
        if getattr(app.battle, "timeout_requested", False) and not getattr(app.battle, "timeout_triggered", False):
            app.battle._check_and_execute_timeout()

        if state == STATE_TIMEOUT:
            if getattr(app, "_timeout_sequence_started", False) and hasattr(app.battle, "_runner") and app.battle._runner.is_done:
                import sys
                if hasattr(app, "qt_win") and app.qt_win:
                    app.qt_win.close()
                elif hasattr(app, "destroy"):
                    app.destroy()
                    sys.exit(0)

    # State transitions
    state = app.battle.state
    if state != app._prev_state:
        if app._prev_state == STATE_MINIGAME and state != STATE_MINIGAME:
            if hasattr(app, "qt_win") and app.qt_win:
                app.qt_win.exit_minigame_hud_mode()
        if app._prev_state == STATE_ATTACK_MINIGAME and state != STATE_ATTACK_MINIGAME:
            if hasattr(app, "qt_win") and app.qt_win:
                app.qt_win.exit_attack_minigame_hud_mode()
        app._on_state_change(state)
    app._prev_state = state

    # Turn checks
    if state == STATE_PLAYER_TURN:
        if (app._turn_start > 0
                and not app.battle.is_executing_action
                and app.battle.action_complete_time == 0):
            lever_pulled = False
            if hasattr(app, "qt_win") and app.qt_win and hasattr(app.qt_win, "actions_overlay"):
                lever_pulled = getattr(app.qt_win.actions_overlay, "lever_pulled", False)

            elapsed = time.time() - app._turn_start
            # Limite de tempo removido a pedido do jogador
            # if elapsed >= PLAYER_TURN_TIMEOUT and not app._timed_out and not lever_pulled:
            #     app._timed_out = True
            #     app.hud.show_banner("TEMPO ESGOTADO!", C_ORANGE)
            #     app._on_action_selected("atk0")

        if (app.battle.is_executing_action
                or app.battle.action_complete_time > 0):
            app.battle.check_player_action_completion()

    elif state == STATE_ATTACK_MINIGAME and app.active_attack_minigame:
        pr = app.battle.player_robot if (app.battle and hasattr(app.battle, "player_robot")) else "PLAYER"
        hand_pos = app._finger_pos_norm
        hand_closed = False
        if app._input_mode == "cv" and app.cv_input:
            _, hand_closed = app.cv_input.update()
        elif app._input_mode == "mouse":
            hand_closed = app._mouse_pressed

        app.active_attack_minigame.update(hand_pos, hand_closed, dt)

        if hasattr(app, "qt_win") and app.qt_win:
            if hand_pos:
                app.qt_win.attack_minigame_overlay.set_hand_pos(hand_pos[0], hand_pos[1])
            else:
                app.qt_win.attack_minigame_overlay.set_hand_pos(None, None)

        if app.active_attack_minigame.__class__.__name__ == "MeteorStompMinigame":
            pass
        elif app.active_attack_minigame.__class__.__name__ == "BlizzardSlashMinigame":
            if pr and hasattr(pr, "v_h"):
                pr.v_h = (pr.v_h + 35.0 * dt) % 360.0
                pr.target_h = pr.v_h

        if app.active_attack_minigame.is_finished():
            result = app.active_attack_minigame.get_result()
            action = app.selected_attack_action
            
            if app.active_attack_minigame.__class__.__name__ == "DanceNightMinigame":
                app.battle.dance_hits = getattr(app.active_attack_minigame, "_hits", 0)
            elif app.active_attack_minigame.__class__.__name__ == "BlizzardSlashMinigame":
                app.battle.blizzard_charge = getattr(app.active_attack_minigame, "_charge", 0.0)
            elif app.active_attack_minigame.__class__.__name__ == "SymphonyWaveMinigame":
                app.battle.symphony_tile_offset = getattr(app.active_attack_minigame, "_tile_offset", 0)

            app.active_attack_minigame = None
            app.selected_attack_action = None

            from game.combat.serial_controller import get_serial_controller
            get_serial_controller().send_command_realtime(pr, "STOP", 0)

            if hasattr(app, "qt_win") and app.qt_win:
                app.qt_win.exit_attack_minigame_hud_mode()

            app.battle.execute_player_action(action, result)
            app.battle.state = STATE_PLAYER_TURN
            app.battle.is_executing_action = True


    # HUD integration update
    app.hud.update(
        dt, app._battle_log, app._action_hover,
        app._hover_timer, app._turn_start,
        app._finger_pos_norm,
        app._screen_w, app._screen_h,
    )

    return Task.cont

def sync_robot_nodes(app):
    from engine.render.robot_node import RobotNode
    robots = {}
    if app.battle.player_robot:
        robots["player"] = app.battle.player_robot
    if app.battle.ia_robot:
        robots["ia"] = app.battle.ia_robot

    for key, r in robots.items():
        if key not in app._robot_nodes:
            app._robot_nodes[key] = RobotNode(app.render, r, app.loader)

    for key in list(app._robot_nodes.keys()):
        if key not in robots:
            app._robot_nodes[key].destroy()
            del app._robot_nodes[key]

def update_tile_highlights(app):
    pr = app.battle.player_robot
    ia = app.battle.ia_robot
    state = app.battle.state

    warn_cols = []
    if state == STATE_MINIGAME and hasattr(app.battle, "minigame_attack_dir"):
        if app.battle.minigame_attack_dir == "left":
            warn_cols = [0, 1, 2]
        elif app.battle.minigame_attack_dir == "right":
            warn_cols = [2, 3, 4]

    for row_i, row in enumerate(app._tiles):
        for col_i, tile in enumerate(row):
            on_player = pr and round(pr.v_ty) == row_i and round(pr.v_tx) == col_i
            on_ia     = ia and round(ia.v_ty) == row_i and round(ia.v_tx) == col_i
            tile.set_highlight(on_player or on_ia)
            tile.set_warning(col_i in warn_cols)
