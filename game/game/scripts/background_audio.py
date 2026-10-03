import asyncio
from game.champions.robot_base import PLAY_SOUND

async def background_audio_sequence(ctx):
    """
    Sequência paralela que roda durante o jogo inteiro.
    Usa asyncio.sleep() para contar o tempo e PLAY_SOUND para tocar áudio.
    """
    print("[BackgroundAudio] Iniciando sequência paralela de áudio...")
    
    # Exemplo: Espera 5 segundos e toca um som
    await asyncio.sleep(5.0)
    print("[BackgroundAudio] 5 segundos atingidos! Tocando som...")
    await PLAY_SOUND(ctx, "assets/sounds/whoosh.wav")
    
    # Exemplo: Espera mais 10 segundos e toca outro som
    await asyncio.sleep(10.0)
    print("[BackgroundAudio] 15 segundos atingidos! Tocando som...")
    await PLAY_SOUND(ctx, "assets/sounds/whoosh.wav")
    
    print("[BackgroundAudio] Sequência de áudio paralela finalizada.")
