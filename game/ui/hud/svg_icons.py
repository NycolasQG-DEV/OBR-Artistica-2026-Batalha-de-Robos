# ui/hud/svg_icons.py — Ícones SVG profissionais centralizados (inline strings)
"""
Módulo centralizado com todas as constantes SVG usadas no projeto.
Cada ícone é uma string SVG inline que pode ser renderizada via QSvgRenderer.
"""

# ── Mão Aberta (✋) ──────────────────────────────────────────────────
SVG_HAND_OPEN = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M32 4c-1.5 0-2.8 1.2-2.8 2.8v22c0 .8-.7 1.5-1.5 1.5s-1.5-.7-1.5-1.5V10c0-1.5-1.2-2.8-2.8-2.8S20.6 8.5 20.6 10v20.5c0 .8-.7 1.5-1.5 1.5s-1.5-.7-1.5-1.5V14.3c0-1.5-1.2-2.8-2.8-2.8S12 12.8 12 14.3v21c0 .8-.3 1.5-.8 2L8 40.5c-1.3 1.3-1.3 3.4 0 4.7l8.5 10c2.5 3 6.2 4.8 10.2 4.8h8.6c7.7 0 14-6.3 14-14V18c0-1.5-1.2-2.8-2.8-2.8S43.8 16.5 43.8 18v10.8c0 .8-.7 1.5-1.5 1.5s-1.5-.7-1.5-1.5V6.8c0-1.5-1.3-2.8-2.8-2.8h-6z" fill="white" stroke="rgba(0,236,255,0.8)" stroke-width="1.5"/>
</svg>'''

# ── Raio / Energia (⚡) ──────────────────────────────────────────────
SVG_LIGHTNING = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M38 2L14 36h14L22 62l28-38H36L44 2H38z" fill="#00ecff" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
</svg>'''

# ── Triângulo de Alerta (⚠️) ─────────────────────────────────────────
SVG_WARNING = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M32 6L4 58h56L32 6z" fill="#ffcc00" stroke="#ff6600" stroke-width="2" stroke-linejoin="round"/>
  <rect x="29" y="24" width="6" height="18" rx="3" fill="#1a1a1a"/>
  <circle cx="32" cy="48" r="3.5" fill="#1a1a1a"/>
</svg>'''

# ── Checkmark / Confirmação (✅) ─────────────────────────────────────
SVG_CHECKMARK = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <circle cx="32" cy="32" r="28" fill="#23ff78" opacity="0.2"/>
  <circle cx="32" cy="32" r="28" stroke="#23ff78" stroke-width="3" fill="none"/>
  <path d="M18 32l10 10 18-20" stroke="white" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>'''

# ── Cruz / Bloqueio (❌) ─────────────────────────────────────────────
SVG_CROSS = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <circle cx="32" cy="32" r="28" fill="#ff3333" opacity="0.2"/>
  <circle cx="32" cy="32" r="28" stroke="#ff3333" stroke-width="3" fill="none"/>
  <path d="M20 20l24 24M44 20L20 44" stroke="white" stroke-width="5" stroke-linecap="round" fill="none"/>
</svg>'''

# ── Crânio / Boss (☠) ────────────────────────────────────────────────
SVG_SKULL = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <ellipse cx="32" cy="28" rx="22" ry="24" fill="white" stroke="#aaa" stroke-width="1.5"/>
  <ellipse cx="23" cy="26" rx="6" ry="7" fill="#1a1a2e"/>
  <ellipse cx="41" cy="26" rx="6" ry="7" fill="#1a1a2e"/>
  <path d="M24 42v8M32 42v10M40 42v8" stroke="white" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M22 40c3 3 7 4 10 4s7-1 10-4" stroke="#aaa" stroke-width="1.5" fill="none"/>
</svg>'''

# ── Fogo / DinoByte (🔥) ─────────────────────────────────────────────
SVG_FIRE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M32 4c0 0-16 16-16 32 0 12 7.2 20 16 24 8.8-4 16-12 16-24C48 20 32 4 32 4z" fill="#ff6600"/>
  <path d="M32 18c0 0-8 10-8 20s3.6 14 8 16c4.4-2 8-6 8-16S32 18 32 18z" fill="#ffcc00"/>
  <path d="M32 32c0 0-3 5-3 10s1.4 7 3 8c1.6-1 3-3 3-8S32 32 32 32z" fill="#ffffff" opacity="0.7"/>
</svg>'''

# ── Floco de Neve / PenLinux (❄) ─────────────────────────────────────
SVG_SNOWFLAKE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <g stroke="#55b5ff" stroke-width="3" stroke-linecap="round">
    <line x1="32" y1="4" x2="32" y2="60"/>
    <line x1="8" y1="18" x2="56" y2="46"/>
    <line x1="8" y1="46" x2="56" y2="18"/>
    <line x1="32" y1="4" x2="26" y2="12"/>
    <line x1="32" y1="4" x2="38" y2="12"/>
    <line x1="32" y1="60" x2="26" y2="52"/>
    <line x1="32" y1="60" x2="38" y2="52"/>
    <line x1="8" y1="18" x2="16" y2="20"/>
    <line x1="8" y1="18" x2="12" y2="12"/>
    <line x1="56" y1="46" x2="48" y2="44"/>
    <line x1="56" y1="46" x2="52" y2="52"/>
    <line x1="8" y1="46" x2="16" y2="44"/>
    <line x1="8" y1="46" x2="12" y2="52"/>
    <line x1="56" y1="18" x2="48" y2="20"/>
    <line x1="56" y1="18" x2="52" y2="12"/>
  </g>
</svg>'''

# ── Meteoro (☄️) ──────────────────────────────────────────────────────
SVG_METEOR = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <ellipse cx="36" cy="36" rx="18" ry="16" fill="#8B4513" stroke="#ff6600" stroke-width="2"/>
  <ellipse cx="36" cy="36" rx="12" ry="10" fill="#a0522d"/>
  <path d="M20 28L4 4" stroke="#ffcc00" stroke-width="4" stroke-linecap="round" opacity="0.8"/>
  <path d="M24 22L12 8" stroke="#ff9900" stroke-width="3" stroke-linecap="round" opacity="0.6"/>
  <path d="M18 34L2 18" stroke="#ff6600" stroke-width="3" stroke-linecap="round" opacity="0.5"/>
  <ellipse cx="30" cy="32" rx="4" ry="3" fill="#d2691e" opacity="0.6"/>
</svg>'''

# ── Ciclone / Blizzard (🌀) ──────────────────────────────────────────
SVG_CYCLONE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M32 8a24 24 0 0 1 0 48" stroke="#55b5ff" stroke-width="4" stroke-linecap="round" fill="none"/>
  <path d="M32 14a18 18 0 0 0 0 36" stroke="#88d4ff" stroke-width="3" stroke-linecap="round" fill="none"/>
  <path d="M32 20a12 12 0 0 1 0 24" stroke="#bbefff" stroke-width="2.5" stroke-linecap="round" fill="none"/>
  <circle cx="32" cy="32" r="4" fill="white"/>
</svg>'''

# ── Setas de Combo (🔄) ──────────────────────────────────────────────
SVG_ARROWS = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M44 16a18 18 0 0 1 0 32" stroke="#00ecff" stroke-width="4" stroke-linecap="round" fill="none"/>
  <path d="M20 48a18 18 0 0 1 0-32" stroke="#00ecff" stroke-width="4" stroke-linecap="round" fill="none"/>
  <polygon points="44,12 52,18 44,24" fill="#00ecff"/>
  <polygon points="20,40 12,46 20,52" fill="#00ecff"/>
</svg>'''

# ── Robô Genérico (🤖) ──────────────────────────────────────────────
SVG_ROBOT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <rect x="16" y="20" width="32" height="28" rx="6" fill="#3a3a5c" stroke="#00ecff" stroke-width="2"/>
  <rect x="20" y="50" width="10" height="8" rx="2" fill="#3a3a5c" stroke="#00ecff" stroke-width="1.5"/>
  <rect x="34" y="50" width="10" height="8" rx="2" fill="#3a3a5c" stroke="#00ecff" stroke-width="1.5"/>
  <circle cx="26" cy="32" r="5" fill="#00ecff"/>
  <circle cx="38" cy="32" r="5" fill="#00ecff"/>
  <rect x="24" y="40" width="16" height="4" rx="2" fill="#00ecff" opacity="0.6"/>
  <line x1="32" y1="12" x2="32" y2="20" stroke="#00ecff" stroke-width="2"/>
  <circle cx="32" cy="10" r="3" fill="#00ecff"/>
</svg>'''

# ── Seta para Baixo (⬇️) ─────────────────────────────────────────────
SVG_ARROW_DOWN = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M32 8v40M18 38l14 14 14-14" stroke="#00ecff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>'''

# ── Perfeito / Excelente (estrela) ───────────────────────────────────
SVG_PERFECT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <path d="M32 4l8 16 18 3-13 12 3 18-16-8-16 8 3-18L6 23l18-3z" fill="#23ff78" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
</svg>'''


# ══════════════════════════════════════════════════════════════════════
# Helper para renderizar SVG como QPixmap
# ══════════════════════════════════════════════════════════════════════

def svg_to_pixmap(svg_str: str, size: int = 32):
    """Converte uma string SVG para QPixmap de dimensão size x size."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QPixmap, QPainter
    from PySide6.QtSvg import QSvgRenderer

    data = QByteArray(svg_str.encode('utf-8'))
    renderer = QSvgRenderer(data)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def svg_to_icon_label(svg_str: str, size: int = 24, parent=None):
    """Cria um QLabel contendo o ícone SVG renderizado como pixmap."""
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import Qt

    pixmap = svg_to_pixmap(svg_str, size)
    lbl = QLabel(parent)
    lbl.setPixmap(pixmap)
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet("background: transparent; border: none;")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def render_svg_on_painter(painter, svg_str: str, x: int, y: int, size: int):
    """Renderiza uma string SVG diretamente num QPainter ativo, na posição e tamanho especificados."""
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtSvg import QSvgRenderer

    data = QByteArray(svg_str.encode('utf-8'))
    renderer = QSvgRenderer(data)
    renderer.render(painter, QRectF(x, y, size, size))
