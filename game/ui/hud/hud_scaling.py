# ui/hud/hud_scaling.py — funções utilitárias para escala de interface
from game.config.ui import BASE_DESIGN_WIDTH, BASE_DESIGN_HEIGHT, UI_SCALE_MIN, UI_SCALE_MAX

def compute_ui_scale(viewport_width: float, viewport_height: float) -> float:
    """Calcula a escala da UI proporcional à resolução base de design e dentro dos limites definidos."""
    scale = min(viewport_width / BASE_DESIGN_WIDTH, viewport_height / BASE_DESIGN_HEIGHT)
    return max(UI_SCALE_MIN, min(scale, UI_SCALE_MAX))
