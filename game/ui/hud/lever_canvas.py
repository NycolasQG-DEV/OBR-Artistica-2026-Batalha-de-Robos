from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QLinearGradient
from PySide6.QtWidgets import QWidget

class LeverCanvas(QWidget):
    """
    Canvas da Alavanca Estilo Duolingo (Extra Larga e Limpa):
    - Puxador 'T' vermelho extra grosso e largo horizontalmente com acabamento 3D Duolingo.
    - Sem a tag/marca visual de 50% (mantendo a função de auto-drop ativa em background).
    - Sem botões adicionais na tela.
    """
    auto_pull_triggered = Signal()

    def __init__(self, hand_renderer=None, parent=None, accent_color="#ff4b4b"):
        super().__init__(parent)
        self._hand_renderer = hand_renderer
        self._pct = 0.0
        self._holding = False
        self._is_auto_pulling = False
        self._mouse_drag = False
        self._accent_color = QColor(accent_color)
        
        # Timer de retorno suave (soltou antes dos 50%)
        self._spring_timer = QTimer(self)
        self._spring_timer.setInterval(16)
        self._spring_timer.timeout.connect(self._spring_step)

        # Timer de auto-pull (atingiu 50%, desce o resto sozinho)
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(16)
        self._auto_timer.timeout.connect(self._auto_pull_step)

    def reset(self):
        self._spring_timer.stop()
        self._auto_timer.stop()
        self._pct = 0.0
        self._holding = False
        self._is_auto_pulling = False
        self._mouse_drag = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._mouse_drag = True
            self._drag_start_y = event.position().y()
            self.set_progress(10.0, True)

    def mouseMoveEvent(self, event):
        if getattr(self, "_mouse_drag", False):
            dy = event.position().y() - getattr(self, "_drag_start_y", event.position().y())
            pull_h = max(1.0, float(self.height() - 46))
            pct = max(0.0, min(100.0, (dy / pull_h) * 100.0))
            self.set_progress(pct, True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._mouse_drag = False
            if self._pct >= 70.0:
                self._start_auto_pull()
            else:
                self.set_progress(0.0, False)

    def set_progress(self, pct: float, holding: bool):
        if self._is_auto_pulling:
            return

        pct = max(0.0, min(100.0, pct))
        
        # Trava de 70%: engata o descolamento automático silenciosamente
        if pct >= 70.0 and holding:
            self._start_auto_pull()
            return

        if holding:
            self._spring_timer.stop()
            self._pct = pct
            self._holding = True
            self.update()
        else:
            if self._holding and self._pct > 0:
                self._holding = False
                self._spring_timer.start()
            elif not self._spring_timer.isActive():
                self._pct = 0.0
                self.update()

    def _start_auto_pull(self):
        if self._is_auto_pulling:
            return
        self._is_auto_pulling = True
        self._holding = False
        self._spring_timer.stop()
        self._auto_timer.start()
        self.auto_pull_triggered.emit()

    def _auto_pull_step(self):
        self._pct += 12.0
        if self._pct >= 100.0:
            self._pct = 100.0
            self._auto_timer.stop()
        self.update()

    def _spring_step(self):
        self._pct -= 8.0
        if self._pct <= 0:
            self._pct = 0.0
            self._spring_timer.stop()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        
        # 1. TRILHO VERTICAL GROSSO E ROBUSTO (Extra Largo)
        track_w = 40
        track_h = h - 34
        track_x = (w - track_w) / 2
        track_y = 17

        # Fundo escuro do trilho
        p.setPen(QPen(QColor(0, 0, 0, 180), 4))
        p.setBrush(QColor(18, 22, 34, 230))
        p.drawRoundedRect(track_x, track_y, track_w, track_h, 19, 19)

        # Borda interna colorida do trilho
        p.setPen(QPen(QColor(255, 204, 0, 180), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(track_x + 3, track_y + 3, track_w - 6, track_h - 6, 16, 16)

        # Ranhura central do trilho
        slot_w = 16
        slot_x = (w - slot_w) / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(10, 12, 18, 255))
        p.drawRoundedRect(slot_x, track_y + 8, slot_w, track_h - 16, 8, 8)

        # 2. POSIÇÃO DA ALAVANCA
        handle_height = 46
        min_y = track_y + 6
        max_y = track_y + track_h - handle_height - 6
        current_y = min_y + (max_y - min_y) * (self._pct / 100.0)

        # 3. HASTE METÁLICA GROSSA E LARGA
        shaft_w = 18
        shaft_x = (w - shaft_w) / 2
        shaft_grad = QLinearGradient(shaft_x, 0, shaft_x + shaft_w, 0)
        shaft_grad.setColorAt(0.0, QColor(160, 175, 195))
        shaft_grad.setColorAt(0.5, QColor(255, 255, 255))
        shaft_grad.setColorAt(1.0, QColor(130, 145, 165))
        p.setPen(QPen(QColor(0, 0, 0, 150), 2))
        p.setBrush(shaft_grad)
        p.drawRect(shaft_x, track_y + 6, shaft_w, current_y - track_y + 10)

        # 4. PUXADOR "T" VERMELHO DUOLINGO EXTRA LARGO HORIZONTALMENTE
        t_width = int(w * 0.94)  # Extra largo!
        t_height = 46            # Extra grosso!
        t_x = (w - t_width) / 2
        t_y = current_y

        # Sombra 3D Inferior do Botão Duolingo
        shadow_h = 8
        shadow_color = QColor(180, 20, 45) if not (self._holding or self._is_auto_pulling) else QColor(140, 10, 30)
        p.setPen(Qt.NoPen)
        p.setBrush(shadow_color)
        p.drawRoundedRect(t_x, t_y + shadow_h, t_width, t_height, 18, 18)

        # Face Frontal Vermelha Vívida
        face_color = QColor(255, 75, 75) if not (self._holding or self._is_auto_pulling) else QColor(255, 30, 60)
        p.setPen(QPen(QColor(255, 255, 255, 240), 3.5))
        p.setBrush(face_color)
        p.drawRoundedRect(t_x, t_y, t_width, t_height, 18, 18)

        # Highlight brilhante superior
        p.setPen(QPen(QColor(255, 255, 255, 140), 2.5))
        p.drawLine(int(t_x + 20), int(t_y + 6), int(t_x + t_width - 20), int(t_y + 6))

        # Conector central grosso do T
        joint_w = 30
        joint_h = 14
        joint_x = (w - joint_w) / 2
        p.setPen(QPen(QColor(0, 0, 0, 160), 2))
        p.setBrush(QColor(40, 48, 64, 255))
        p.drawRoundedRect(joint_x, t_y + t_height - 4, joint_w, joint_h, 7, 7)

        p.end()
