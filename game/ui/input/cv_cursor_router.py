# ui/input/cv_cursor_router.py — routing of CV gestures to the Qt UI and automatic clicks via dwell time
import time
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtWidgets import QApplication, QPushButton

class CVCursorRouter:
    def __init__(self, win):
        self.win = win

    def update_cv_cursor(self, nx, ny, closed, hands_data=None):
        """Processes Computer Vision gesture coordinates over Qt UI."""
        from game.combat.battle_logic import STATE_MINIGAME
        is_minigame = False
        if self.win.panda_app and hasattr(self.win.panda_app, "battle") and self.win.panda_app.battle:
            if self.win.panda_app.battle.state == STATE_MINIGAME:
                is_minigame = True

        if is_minigame or nx is None or ny is None:
            self.win.cv_cursor.set_cursor_state(None, None, 0.0, False, None)
            self.win._hovered_widget = None
            self.win._hover_start_time = None
            # Mesmo sem posição, notifica o actions_overlay para que ele possa
            # resetar estados internos (ex: alavanca) quando a mão some da câmera
            if hasattr(self.win, "actions_overlay") and self.win.actions_overlay.isVisible():
                self.win.actions_overlay.update_cv_gesture(None, None, False)
            return

        # Map normalized coordinate space (0-1) to pixel coords
        px = int(nx * self.win.width())
        py = int(ny * self.win.height())
        global_pos = self.win.mapToGlobal(QPoint(px, py))

        # Find widget under CV coordinate
        target_widget = QApplication.widgetAt(global_pos)

        # Avoid cursor target hitting the cv_cursor overlay itself
        if target_widget and (target_widget == self.win.cv_cursor or self.win.cv_cursor.isAncestorOf(target_widget)):
            target_widget = None

        # Check if first attack/turn has been reached
        if not getattr(self.win, "_first_attack_reached", False):
            from game.combat.battle_logic import STATE_PLAYER_TURN
            if self.win.panda_app and hasattr(self.win.panda_app, "battle") and self.win.panda_app.battle:
                if self.win.panda_app.battle.state == STATE_PLAYER_TURN:
                    self.win._first_attack_reached = True

        # Route gesture to actions overlay if active
        actions_active = hasattr(self.win, "actions_overlay") and self.win.actions_overlay.isVisible()
        if actions_active:
            self.win.actions_overlay.update_cv_gesture(nx, ny, closed)

        hover_pct = 0.0
        lever_canvas = None

        if target_widget and not actions_active and getattr(self.win, "_first_attack_reached", False):
            clickable = None

            if getattr(self.win, "_global_lever_state", 0) == 1 and getattr(self.win, "_hovered_widget", None):
                clickable = self.win._hovered_widget
            else:
                curr = target_widget
                while curr:
                    if isinstance(curr, QPushButton):
                        clickable = curr
                        break
                    curr = curr.parentWidget()

            lever_canvas = getattr(clickable, "lever_canvas", None) if clickable else None

            if clickable and clickable.isEnabled():
                if getattr(self.win, "_hovered_widget", None) != clickable and getattr(self.win, "_global_lever_state", 0) == 0:
                    self.win._hovered_widget = clickable
                    self.win._global_lever_state = 0
                    if lever_canvas: lever_canvas.set_progress(0.0, False)

                if lever_canvas:
                    if getattr(self.win, "_global_lever_state", 0) == 0:
                        if not closed:
                            self.win._lever_ready = True
                            lever_canvas.set_progress(0.0, False)
                        elif closed and getattr(self.win, "_lever_ready", False):
                            self.win._global_lever_state = 1
                            self.win._lever_start_ny = ny
                            self.win._lever_ready = False
                            lever_canvas.set_progress(0.0, True)
                    elif self.win._global_lever_state == 1:
                        if not closed:
                            self.win._global_lever_state = 0
                            lever_canvas.set_progress(0.0, False)
                        else:
                            delta_y = ny - getattr(self.win, "_lever_start_ny", ny)
                            pull_dist = 0.40
                            hover_pct = max(0.0, min(100.0, (delta_y / pull_dist) * 100.0))

                            # Puxa automaticamente o restante a partir de 30%
                            if hover_pct >= 30.0:
                                hover_pct = 100.0

                            lever_canvas.set_progress(hover_pct, True)

                            if hover_pct >= 100.0:
                                clickable.click()
                                self.win._global_lever_state = 0
                                hover_pct = 0.0
                                self.win._hovered_widget = None
                                self.win._lever_ready = False
                                lever_canvas.set_progress(0.0, False)
                else:
                    if getattr(self.win, "_hovered_widget", None) != clickable or getattr(self.win, "_hover_start_time", None) is None:
                        self.win._hovered_widget = clickable
                        self.win._hover_start_time = time.time()
                    else:
                        elapsed = time.time() - self.win._hover_start_time
                        hover_pct = min(100.0, (elapsed / 1.5) * 100.0)
                        if hover_pct >= 100.0:
                            clickable.click()
                            self.win._hover_start_time = time.time() + 10000.0
                            hover_pct = 0.0
            else:
                self.win._hovered_widget = None
                self.win._global_lever_state = 0
                if lever_canvas: lever_canvas.set_progress(0.0, False)
        else:
            self.win._hovered_widget = None
            self.win._global_lever_state = 0
            if lever_canvas: lever_canvas.set_progress(0.0, False)

        self.win._prev_hand_closed = closed
        if lever_canvas:
            self.win.cv_cursor.set_cursor_state(global_pos.x(), global_pos.y(), 0.0, closed, hands_data)
        else:
            self.win.cv_cursor.set_cursor_state(global_pos.x(), global_pos.y(), hover_pct, closed, hands_data)
