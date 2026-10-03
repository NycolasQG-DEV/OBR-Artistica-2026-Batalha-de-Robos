# engine/ui_kit/animations.py — animações genéricas de UI Qt
from PySide6.QtCore import QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect


# ── FADE IN ANIMATION HELPER ──────────────────────────────────────────
def fade_in_widget(widget, duration=650):
    """Applies a smooth fade-in animation to a QWidget using Qt properties."""
    from PySide6.QtCore import Qt
    is_window = bool(widget.windowFlags() & Qt.Window)
    
    if is_window:
        widget.setWindowOpacity(0.0)
        widget.show()
        widget.raise_()
        
        anim = QPropertyAnimation(widget, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        
        widget._fade_anim = anim
        anim.start()
    else:
        effect = widget.graphicsEffect()
        if not effect or not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        effect.setOpacity(0.0)
        widget.show()
        widget.raise_()

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        
        def on_finished():
            widget.setGraphicsEffect(None)
        anim.finished.connect(on_finished)
        
        widget._fade_anim = anim
        anim.start()


def slide_fade_in_boss_bar(widget, duration=600):
    """Applies a combined slide-down and fade-in animation with an elastic bounce at the end."""
    # Stop any previous running animations on the widget to prevent conflicts and ensure position resets
    if hasattr(widget, "_pos_anim") and widget._pos_anim:
        try:
            widget._pos_anim.stop()
        except Exception:
            pass
    if hasattr(widget, "_fade_anim") and widget._fade_anim:
        try:
            widget._fade_anim.stop()
        except Exception:
            pass

    # Ensure position is correctly calculated first
    parent = widget.parent()
    if parent and hasattr(parent, "_reposition_overlays"):
        parent._reposition_overlays()

    from PySide6.QtCore import Qt
    is_window = bool(widget.windowFlags() & Qt.Window)
    
    if is_window:
        widget.setWindowOpacity(0.0)
    else:
        effect = widget.graphicsEffect()
        if not effect or not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
    
    widget.show()
    widget.raise_()

    if is_window:
        opacity_anim = QPropertyAnimation(widget, b"windowOpacity")
    else:
        opacity_anim = QPropertyAnimation(effect, b"opacity")
        
    opacity_anim.setDuration(duration)
    opacity_anim.setStartValue(0.0)
    opacity_anim.setEndValue(1.0)
    opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

    pos_anim = QPropertyAnimation(widget, b"pos")
    pos_anim.setDuration(duration)
    
    target_pos = widget.pos()
    start_pos = QPoint(target_pos.x(), target_pos.y() - 40)
    
    # Temporarily move to start position to animate from there
    widget.move(start_pos)
    
    pos_anim.setStartValue(start_pos)
    pos_anim.setEndValue(target_pos)
    pos_anim.setEasingCurve(QEasingCurve.OutBack)  # Nice elastic bounce!
    
    if not is_window:
        def on_finished():
            widget.setGraphicsEffect(None)
        opacity_anim.finished.connect(on_finished)
    
    widget._fade_anim = opacity_anim
    widget._pos_anim = pos_anim
    opacity_anim.start()
    pos_anim.start()


# ── GLOW SHADOW HELPER ────────────────────────────────────────────────
def apply_glow(widget, color_hex, blur=20, offset_y=4):
    """Applies a colored drop-shadow glow to a widget."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setColor(QColor(color_hex))
    shadow.setOffset(0, offset_y)
    widget.setGraphicsEffect(shadow)
    return shadow


# ── FADE OVERLAY HELPER (WINDOW OPACITY) ─────────────────────────────
def fade_overlay(widget, start_opacity: float, end_opacity: float, duration: int, on_finished=None):
    """Anima o windowOpacity de um widget de overlay (janela) de start_opacity até end_opacity."""
    from PySide6.QtCore import QPropertyAnimation
    anim = QPropertyAnimation(widget, b"windowOpacity")
    anim.setDuration(duration)
    anim.setStartValue(start_opacity)
    anim.setEndValue(end_opacity)
    if on_finished:
        anim.finished.connect(on_finished)
    # Guarda referência para evitar coleta de lixo
    widget._fade_overlay_anim = anim
    anim.start()
    return anim

