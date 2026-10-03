# engine/render/effects_factory.py — criação de partículas e textos flutuantes 3D
from engine.render.particles import Particle3D
from engine.render.floating_text import FloatingText3D

def create_floating(app, tx: float, ty: float, text: str, color, size: float = 1.0):
    try:
        ft = FloatingText3D(app, tx, ty, text, color, size=size * 0.055)
        app._floating_texts.append(ft)
    except Exception:
        pass

def create_particles(app, tx: float, ty: float, color, count: int = 12, speed: float = 1.0):
    if not hasattr(app, 'loader') or app.loader is None:
        return
    if not hasattr(app, 'render') or app.render is None:
        return
    for _ in range(min(count, 10)):
        try:
            p = Particle3D(app.render, app.loader, tx, ty, color)
            app._particles.append(p)
        except Exception:
            break

def create_powerup_particles(app, tx: float, ty: float, color, count: int = 15):
    if not hasattr(app, 'loader') or app.loader is None:
        return
    if not hasattr(app, 'render') or app.render is None:
        return
    from engine.render.particles import PowerUpParticle3D
    for _ in range(count):
        try:
            p = PowerUpParticle3D(app.render, app.loader, tx, ty, color)
            app._particles.append(p)
        except Exception:
            break
