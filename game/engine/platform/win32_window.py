import sys
import ctypes
from game.config.ui import BASE_DESIGN_WIDTH, BASE_DESIGN_HEIGHT


def set_dpi_awareness():
    """Configura o Process DPI Awareness no Windows para evitar distorções de escala."""
    if sys.platform == "win32":
        try:
            # PROCESS_SYSTEM_DPI_AWARE = 1
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

def force_foreground(hwnd_id):
    """Força uma janela ao primeiro plano no Windows."""
    if sys.platform == "win32" and hwnd_id:
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd_id)
            ctypes.windll.user32.BringWindowToTop(hwnd_id)
            ctypes.windll.user32.SetActiveWindow(hwnd_id)
            ctypes.windll.user32.FlashWindow(hwnd_id, True)
        except Exception as e:
            print(f"[win32_window] Erro ao forçar primeiro plano: {e}")

def force_foreground_simple(hwnd_id):
    """Força primeiro plano simplificado (sem flash)."""
    if sys.platform == "win32" and hwnd_id:
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd_id)
            ctypes.windll.user32.BringWindowToTop(hwnd_id)
        except Exception:
            pass

def get_system_metrics_screen_size():
    """Retorna a resolução da tela do sistema via Win32 API."""
    if sys.platform == "win32":
        try:
            pw = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
            ph = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
            return pw, ph
        except Exception:
            pass
    return int(BASE_DESIGN_WIDTH), int(BASE_DESIGN_HEIGHT)

def get_physical_container_size(hwnd_id, fallback_w, fallback_h):
    """Retorna o tamanho físico do container do HWND em pixels reais no Windows, ou fallback."""
    if sys.platform == "win32" and hwnd_id:
        try:
            from ctypes import wintypes
            rect = wintypes.RECT()
            if ctypes.windll.user32.GetClientRect(hwnd_id, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 0 and h > 0:
                    return w, h
        except Exception:
            pass
    return fallback_w, fallback_h

def find_panda_hwnd(container_hwnd):
    """Encontra o handle HWND do processo/janela filha do Panda3D no Windows."""
    if sys.platform == "win32" and container_hwnd:
        try:
            # Tenta encontrar especificamente pela classe PandaWindow
            child_hwnd = ctypes.windll.user32.FindWindowExW(container_hwnd, 0, "PandaWindow", None)
            if child_hwnd:
                return child_hwnd
            # Fallback: pega a primeira janela filha
            child_hwnd = ctypes.windll.user32.GetWindow(container_hwnd, 5)  # GW_CHILD
            if child_hwnd:
                return child_hwnd
        except Exception as e:
            print(f"[win32_window] Erro ao buscar child window Panda3D: {e}")
    return None

def move_window(hwnd_id, w, h):
    """Redimensiona e move a janela filha para preencher o container no Windows."""
    if sys.platform == "win32" and hwnd_id:
        try:
            ctypes.windll.user32.MoveWindow(hwnd_id, 0, 0, w, h, True)
            return True
        except Exception as e:
            print(f"[win32_window] Erro ao mover janela: {e}")
    return False
