# game/minigames/timeout_sequence.py
# ═══════════════════════════════════════════════════════════════════════
# Sequência Cinematográfica Assíncrona pós-Timeout — Great Intelligence
# ═══════════════════════════════════════════════════════════════════════

import asyncio
from panda3d.core import Point3

async def execute_timeout_sequence(app, camera, battle):
    """
    Executa a sequência cinematográfica assíncrona quando o timer do combate expira:
    1. A câmera foca na Great Intelligence atrás do robô do jogador (PenLinux).
    2. A Great Intelligence faz fade out deslizando para baixo com som de 'WOOSH'.
    3. A câmera dá uma volta cinematográfica completa pela arena (esperando 6s).
    4. A câmera muda rapidamente para a visão lateral (referência do lado direito do robô do jogador).
    5. Ocorre um tremo de câmera muito forte (camera shake) por 3s.
    6. A Great Intelligence reaparece de cima para baixo no lado oposto atrás da arena.
    """
    from game.champions.robot_base import DELAY
    from engine.render.geometry import grid_to_world

    pr = getattr(battle, "player_robot", None)
    gi = getattr(app, "great_intelligence", None)

    # 1. Foco inicial na Great Intelligence (atrás do PenLinux)
    if camera:
        camera._mode = camera.MODE_ACTION
        if gi and hasattr(gi, "root"):
            pos = gi.root.getPos()
            camera._target_center = Point3(pos.getX(), pos.getY(), pos.getZ() + 1.0)
        elif pr:
            wp = grid_to_world(pr.v_tx, pr.v_ty)
            camera._target_center = Point3(wp.getX(), wp.getY(), 1.5)
        
        camera._target_dist = 12.0
        camera._target_heading = 0.0
        camera._target_pitch = -10.0
        camera.set_camera_speed("fast")

    await DELAY(0.5)

    # 2. Toca o som de "WOOSH"
    if app and hasattr(app, "loader") and app.loader:
        try:
            whoosh_sfx = app.loader.loadSfx("assets/sounds/whoosh.wav")
            if whoosh_sfx:
                whoosh_sfx.play()
        except Exception as e:
            print(f"[TimeoutSequence] Erro ao tocar som whoosh: {e}")

    # 3. Fade Out + Deslizar para baixo da Great Intelligence
    if gi:
        slide_duration = 1.2
        steps = 30
        dt_step = slide_duration / steps
        for i in range(steps):
            frac = (i + 1) / steps
            gi.offset_z = -12.0 * frac
            gi.set_alpha(1.0 - frac)
            await asyncio.sleep(dt_step)

    # (Giro cinematográfico pela arena removido a pedido)

    # 5. Mudança RÁPIDA para a visão lateral (referência do lado direito do robô do jogador)
    if camera:
        camera._mode = camera.MODE_ACTION
        if pr:
            wp = grid_to_world(pr.v_tx, pr.v_ty)
            camera._target_center = Point3(wp.getX(), wp.getY(), 1.2)
        else:
            camera._target_center = Point3(0.0, 0.0, 1.2)
        
        # Visão com referência do lado direito do robô do jogador (+90.0)
        camera._target_heading = 90.0
        camera._target_dist = 11.0
        camera._target_pitch = -8.0
        camera.set_camera_speed("fast")

    await DELAY(0.3)

    # 6. Camera Shake BEM FORTE por 3s + Reaparecimento da Great Intelligence no lado oposto atrás da arena
    if camera:
        camera.shake(0.75, duration=3.0)

    # Toca o som de retorno quando a Great Intelligence reaparece
    if app and hasattr(app, "loader") and app.loader:
        try:
            return_sfx = app.loader.loadSfx("assets/sounds/whoosh.wav")
            if return_sfx:
                return_sfx.play()
        except Exception as e:
            print(f"[TimeoutSequence] Erro ao tocar som de retorno: {e}")

    # Posição no lado oposto atrás da arena e rotação de -90° para olhar para a tela
    if gi:
        gi.set_custom_pos(Point3(-5.0, 0, -6.5))
        gi.set_rotation_offset(-270.0)  # Gira -90° a partir do ângulo base para olhar para a tela
        gi.offset_z = 18.0  # Começa bem no alto
        gi.set_alpha(0.0)   # Começa transparente

        shake_duration = 3.0
        steps = 50
        dt_step = shake_duration / steps
        for i in range(steps):
            frac = (i + 1) / steps
            gi.offset_z = 18.0 * (1.0 - frac)  # Desliza de cima para baixo
            gi.set_alpha(frac)                 # Fade in de 0 a 1
            await asyncio.sleep(dt_step)

    await DELAY(0.5)

    if camera:
        camera.reset_to_battle_view()

    # Encerra o jogo fechand o aplicativo ao concluir a sequência de timeout
    import sys
    if hasattr(app, "qt_win") and app.qt_win:
        app.qt_win.close()
    elif hasattr(app, "destroy"):
        app.destroy()
        sys.exit(0)

    return True
