"""系统文件管理器与窗口互操作。

把「打开目录、让资源管理器窗口前置、把跑到屏幕外的窗口挪回来」这些
Windows 细节集中在一处，主窗口只调用 `open_local_path` 和
`focus_in_explorer`，不必再直接摆弄 Win32 句柄。
"""

import os
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices

# 资源管理器窗口不会立刻出现，用定时器重试而不是阻塞界面
FOCUS_ATTEMPTS = 15
FOCUS_INTERVAL_MS = 120


def open_local_path(path):
    """用系统文件管理器打开本地目录或文件，返回是否成功。"""
    path = Path(path)

    if os.name != "nt":
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    try:
        os.startfile(str(path))
    except OSError:
        return False

    return True


def focus_in_explorer(directory):
    """把打开了该目录的资源管理器窗口提到前台。"""
    if os.name != "nt":
        return

    directory = Path(directory)

    def attempt(remaining):
        hwnd = _find_explorer_window(directory)

        if hwnd is not None:
            _raise_window(hwnd)
            return

        if remaining > 1:
            QTimer.singleShot(
                FOCUS_INTERVAL_MS,
                lambda: attempt(remaining - 1),
            )

    QTimer.singleShot(0, lambda: attempt(FOCUS_ATTEMPTS))


def _user32():
    import ctypes

    return ctypes.windll.user32


def _find_explorer_window(directory):
    """返回打开了指定目录的资源管理器窗口句柄，找不到返回 None。"""
    import ctypes
    from ctypes import wintypes

    user32 = _user32()
    enum_proc_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )
    user32.GetClassNameW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.EnumWindows.argtypes = [enum_proc_type, wintypes.LPARAM]

    folder_name = directory.name.lower()
    full_path = str(directory).lower()
    matches = []

    def enum_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True

        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)

        if class_name.value != "CabinetWClass":
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        lowered = title.value.lower()

        # 标题带完整路径时优先，避免误认其它同名目录
        if full_path in lowered:
            matches.append((2, hwnd))
        elif folder_name in lowered:
            matches.append((1, hwnd))

        return True

    user32.EnumWindows(enum_proc_type(enum_proc), 0)

    if not matches:
        return None

    return max(matches, key=lambda item: item[0])[1]


def _raise_window(hwnd):
    """绕过前台锁定，把窗口恢复并置顶。"""
    import ctypes
    from ctypes import wintypes

    user32 = _user32()
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.BOOL,
    ]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]

    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    _ensure_on_screen(hwnd)

    foreground = user32.GetForegroundWindow()
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    attached = False

    # 只有前台线程才有置顶权限，临时共享输入队列绕过该限制
    if foreground_thread and target_thread != foreground_thread:
        attached = bool(
            user32.AttachThreadInput(foreground_thread, target_thread, True)
        )

    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(foreground_thread, target_thread, False)


def _ensure_on_screen(hwnd):
    """把落在所有显示器之外的窗口挪回主屏幕。"""
    import ctypes
    from ctypes import wintypes

    user32 = _user32()

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    monitor_default_to_null = 0x00000000
    monitor_default_to_primary = 0x00000001
    swp_nozorder = 0x0004
    swp_noactivate = 0x0010

    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [
        wintypes.HMONITOR,
        ctypes.POINTER(MONITORINFO),
    ]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    # 只要窗口有一部分落在某块屏幕上就保持原样
    if user32.MonitorFromWindow(hwnd, monitor_default_to_null):
        return

    monitor = user32.MonitorFromWindow(hwnd, monitor_default_to_primary)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)

    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return

    rect = RECT()

    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    work = info.rcWork
    work_width = work.right - work.left
    work_height = work.bottom - work.top

    # 比工作区还大的窗口先缩到工作区大小，避免移动后又溢出
    if width <= 0 or width > work_width:
        width = work_width

    if height <= 0 or height > work_height:
        height = work_height

    x = work.left + (work_width - width) // 2
    y = work.top + (work_height - height) // 2

    user32.SetWindowPos(
        hwnd,
        None,
        x,
        y,
        width,
        height,
        swp_nozorder | swp_noactivate,
    )
