"""Capa Windows: DPI, tamano de pantalla y hooks globales de mouse/teclado.

Es el unico modulo que habla ctypes. El resto del proyecto no sabe que existe win32.
"""
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x200, 0x201, 0x202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x204, 0x205
WM_KEYDOWN, WM_SYSKEYDOWN = 0x100, 0x104
WM_KEYUP, WM_SYSKEYUP = 0x101, 0x105
VK_F8, VK_F9, VK_F10, VK_F11, VK_F12, VK_ESCAPE = 0x77, 0x78, 0x79, 0x7A, 0x7B, 0x1B

_WH_KEYBOARD_LL, _WH_MOUSE_LL = 13, 14
_GA_ROOT = 2


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)

user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, wt.DWORD]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.WindowFromPoint.restype = ctypes.c_void_p
user32.WindowFromPoint.argtypes = [POINT]
user32.GetAncestor.restype = ctypes.c_void_p
user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]


def enable_dpi_awareness():
    """Sin esto, en pantallas escaladas las coords del hook no coinciden con las de tk."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        user32.SetProcessDPIAware()


def screen_size():
    """Monitor primario. Solo para colocar la barra en un sitio sensato."""
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def work_area():
    """(x, y, ancho, alto) utiles del monitor primario: descuenta la barra de tareas,
    que es justo donde se escondia el ultimo boton de la barra."""
    rect = wt.RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def virtual_screen():
    """(x, y, ancho, alto) de TODOS los monitores juntos. El origen puede ser negativo
    si hay una pantalla a la izquierda o encima de la principal."""
    return tuple(user32.GetSystemMetrics(m) for m in (76, 77, 78, 79))


def cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def top_window_at(x, y):
    """HWND de la ventana raiz bajo el punto. Las zonas color-key no cuentan."""
    return user32.GetAncestor(ctypes.c_void_p(user32.WindowFromPoint(POINT(x, y))), _GA_ROOT)


def top_window_of(widget):
    return user32.GetAncestor(ctypes.c_void_p(widget.winfo_id()), _GA_ROOT)


def _deref(lparam, kind):
    return ctypes.cast(ctypes.c_void_p(lparam), ctypes.POINTER(kind)).contents


class Hooks:
    """Hooks de bajo nivel. Los callbacks devuelven True para tragarse el evento.

    NUNCA tragarse WM_MOUSEMOVE: el sistema mueve el puntero despues del hook,
    asi que bloquearlo congela el cursor (y entonces no llegan coords nuevas).
    """

    def __init__(self, on_mouse=None, on_key=None):
        self._on_mouse, self._on_key = on_mouse, on_key
        self._procs, self._handles = [], []
        self._held = {}  # vk -> si lo tragamos, para distinguir pulsacion de auto-repeticion

    def install(self):
        self._add(_WH_MOUSE_LL, self._mouse_proc)
        self._add(_WH_KEYBOARD_LL, self._key_proc)

    def uninstall(self):
        for h in self._handles:
            user32.UnhookWindowsHookEx(ctypes.c_void_p(h))
        self._handles.clear()

    def _add(self, kind, fn):
        proc = HOOKPROC(fn)
        self._procs.append(proc)  # sin esta referencia el GC se lo lleva y el proceso muere
        handle = user32.SetWindowsHookExW(kind, proc, None, 0)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handles.append(handle)

    def _mouse_proc(self, code, wparam, lparam):
        if code == 0 and self._on_mouse:
            try:
                pt = _deref(lparam, _MSLLHOOKSTRUCT).pt
                if self._on_mouse(wparam, pt.x, pt.y):
                    return 1
            except Exception:
                pass  # una excepcion aqui tumba el hook entero; mejor dejar pasar el evento
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _key_proc(self, code, wparam, lparam):
        if code == 0 and self._on_key:
            try:
                vk = _deref(lparam, _KBDLLHOOKSTRUCT).vkCode
                if wparam in (WM_KEYUP, WM_SYSKEYUP):
                    self._held.pop(vk, None)
                elif wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    # tener la tecla pulsada repite el KEYDOWN: hay que seguir tragandolo
                    # para que no se cuele abajo, pero sin repetir la accion
                    if vk not in self._held:
                        self._held[vk] = bool(self._on_key(vk))
                    if self._held[vk]:
                        return 1
            except Exception:
                pass
        return user32.CallNextHookEx(None, code, wparam, lparam)
