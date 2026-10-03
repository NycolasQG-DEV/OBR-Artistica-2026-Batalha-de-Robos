import asyncio

# robot_choose_sequence.py — Sequência dinâmica baseada na escolha de campeão
# -----------------------------------------------------------------------------

async def run_sequence(db, pen, selected_champion="PenLinux"):
    """
    Sequência assíncrona executada após a tela de seleção, rodando como um slide dedicado.
    """
    print(f"[RobotChooseSequence] Iniciando sequencia para o campeão selecionado: {selected_champion}")

    if selected_champion == "DinoByte":
        # Se DinoByte foi escolhido, db fará os movimentos e tocará o som
        await db.play_sfx("whoosh.wav")
        await db.move_backward(tiles=1.0)
        await db.turn_left(degrees=90.0)
        await db.move_backward(tiles=1.0)
        
        # PenLinux também pode fazer algo se quiser (pois ambos db e pen estão disponíveis)
        # await pen.turn_right(degrees=90.0)
        
    elif selected_champion == "PenLinux":
        # Se PenLinux foi escolhido, pen fará os movimentos e tocará o som
        await pen.play_sfx("whoosh.wav")
        await pen.move_backward(tiles=1.0)
        await pen.turn_right(degrees=90.0)
        await pen.move_backward(tiles=2.0)
        
        # DinoByte também pode fazer algo se quiser
        # await db.turn_left(degrees=90.0)

    else:
        print("[RobotChooseSequence] Nenhum campeão reconhecido.")

    print("[RobotChooseSequence] Fim da sequencia.")
