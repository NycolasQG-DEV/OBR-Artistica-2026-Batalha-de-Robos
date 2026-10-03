# engine/platform/window_bootstrap.py — window creation, DPI, fullscreen, shortcuts and Panda3D sync
import sys
from typing import Tuple, Optional, Any
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QKeySequence, QShortcut, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import QApplication
from panda3d.core import WindowProperties
from game.config.ui import BASE_DESIGN_WIDTH, BASE_DESIGN_HEIGHT

from engine.platform.win32_window import (
    force_foreground, get_system_metrics_screen_size,
    get_physical_container_size, find_panda_hwnd, move_window
)


class WindowBootstrapMixin:
    """Mixin responsible for bootstrapping Qt Window properties, DPI, and key events."""

    def setup_bootstrap(self) -> None:
        """Configures initial frameless window geometries and fullscreen shortcuts."""
        self.setWindowTitle("Robot Arena 3D")

        # Shortcut for Escape key to close the app
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.esc_shortcut.setContext(Qt.ApplicationShortcut)
        self.esc_shortcut.activated.connect(self.close)

        # Shortcut for F11 key to toggle fullscreen/windowed mode
        self.f11_shortcut = QShortcut(QKeySequence(Qt.Key_F11), self)
        self.f11_shortcut.setContext(Qt.ApplicationShortcut)
        self.f11_shortcut.activated.connect(self.toggle_fullscreen_mode)

        self._is_windowed = False

        # Fullscreen frameless window by default
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        screen = QApplication.primaryScreen()
        screen_geom = screen.geometry()
        self.setGeometry(screen_geom)

    def toggle_fullscreen_mode(self) -> None:
        """Alterna entre Tela Cheia (frameless) e Modo Janela (com bordas e barra de título)."""
        is_currently_windowed = getattr(self, "_is_windowed", False)

        if not is_currently_windowed:
            # Alterna para Modo Janela (Windowed mode)
            self._is_windowed = True
            flags = Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint
            self.setWindowFlags(flags)

            w = int(BASE_DESIGN_WIDTH)
            h = int(BASE_DESIGN_HEIGHT)
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.geometry()
                x = sg.x() + (sg.width() - w) // 2
                y = sg.y() + (sg.height() - h) // 2
                self.setGeometry(x, y, w, h)
            else:
                self.resize(w, h)

            self.showNormal()
        else:
            # Alterna para Modo Tela Cheia (Fullscreen Frameless)
            self._is_windowed = False
            flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            self.setWindowFlags(flags)

            screen = QApplication.primaryScreen()
            if screen:
                self.setGeometry(screen.geometry())
            self.showNormal()

        QApplication.processEvents()
        QTimer.singleShot(50, self._deferred_panda_sync)
        QTimer.singleShot(250, self._deferred_panda_sync)


    def init_panda_window(self) -> Tuple[int, int]:
        """Initializes the embedded child window coordinates for the Panda3D window context."""
        self.showNormal()
        QApplication.processEvents()

        # Force to foreground on Windows
        force_foreground(int(self.winId()))

        # Ensure central widget is processed
        QApplication.processEvents()

        pw, ph = self._physical_container_size()
        if pw <= 0 or ph <= 0:
            pw, ph = get_system_metrics_screen_size()

        print(f"[GameWindow] Init Panda3D at size: {pw}x{ph} "
              f"(container logical={self.panda_container.width()}x{self.panda_container.height()}, "
              f"DPR={self.devicePixelRatio()})")

        return pw, ph

    def start_deferred_sync(self) -> None:
        """Triggers a cascade of deferred resizes to align Panda3D coordinate calculations."""
        # Multiple deferred syncs at increasing intervals to ensure
        # the Panda3D child window fully matches the container.
        QTimer.singleShot(100, self._deferred_panda_sync)
        QTimer.singleShot(400, self._deferred_panda_sync)
        QTimer.singleShot(1000, self._deferred_panda_sync)

    def _physical_container_size(self) -> Tuple[int, int]:
        """Returns the Panda3D container size in TRUE physical pixels."""
        return get_physical_container_size(
            int(self.winId()),
            self.width(),
            self.height()
        )

    def _find_panda_hwnd(self) -> int:
        """Finds the embedded Panda3D window's Win32 HWND handle."""
        return find_panda_hwnd(int(self.panda_container.winId()))

    def _deferred_panda_sync(self) -> None:
        """Re-syncs the embedded Panda3D window size with the container."""
        if not self.panda_app or not hasattr(self.panda_app, "win") or not self.panda_app.win:
            return
        w, h = self._physical_container_size()
        if w <= 0 or h <= 0:
            return

        print(f"[GameWindow] Deferred sync: resizing Panda3D to {w}x{h}")

        # 1. Resize the Win32 child window (Panda3D HWND) to fill its parent
        child_hwnd = self._find_panda_hwnd()
        if child_hwnd:
            move_window(child_hwnd, w, h)

        # 2. Tell Panda3D about the new size
        props = WindowProperties()
        props.setOrigin(0, 0)
        props.setSize(w, h)
        self.panda_app.win.requestProperties(props)

        # 3. Update camera aspect ratio immediately
        if hasattr(self.panda_app, "camLens") and self.panda_app.camLens:
            self.panda_app.camLens.setAspectRatio(float(w) / float(h))

        # 4. Force the game loop's resize detection to re-trigger on the next frame.
        self.panda_app._screen_w = 0
        self.panda_app._screen_h = 0

        self.overlay_manager.reposition_overlays()

    def bootstrap_resize_event(self, event: QResizeEvent) -> None:
        """Callback to resize child Panda3D contexts during system resize signals."""
        if self.panda_app and hasattr(self.panda_app, "win") and self.panda_app.win:
            w, h = self._physical_container_size()
            if w > 0 and h > 0:
                child_hwnd = self._find_panda_hwnd()
                if child_hwnd:
                    move_window(child_hwnd, w, h)

                props = WindowProperties()
                props.setOrigin(0, 0)
                props.setSize(w, h)
                self.panda_app.win.requestProperties(props)
                if hasattr(self.panda_app, "camLens") and self.panda_app.camLens:
                    self.panda_app.camLens.setAspectRatio(float(w) / float(h))

                self.panda_app._screen_w = 0
                self.panda_app._screen_h = 0

    def bootstrap_key_event(self, event: QKeyEvent) -> bool:
        """Handles shortcuts like Escape, R (reset), and F11 (toggle fullscreen)."""
        if self.panda_app:
            if hasattr(self.panda_app, "active_attack_minigame") and self.panda_app.active_attack_minigame:
                if hasattr(self.panda_app.active_attack_minigame, "on_key_press"):
                    if self.panda_app.active_attack_minigame.on_key_press(event.key()):
                        event.accept()
                        return True
            if event.key() == Qt.Key_R:
                self.panda_app._reset()
                event.accept()
                return True
            elif event.key() == Qt.Key_Escape:
                self.close()
                event.accept()
                return True
            elif event.key() == Qt.Key_F12:
                # Tela de debug: ângulo relativo/tarado dos robôs
                self.toggle_debug_overlay()
                event.accept()
                return True
            elif event.key() == Qt.Key_D and (event.modifiers() & Qt.ControlModifier):
                # Ctrl+D: mesmo toggle da tela de debug
                self.toggle_debug_overlay()
                event.accept()
                return True
            elif event.key() == Qt.Key_F11:
                # Toggle fullscreen / windowed mode
                self.toggle_fullscreen_mode()
                event.accept()
                return True
        return False

