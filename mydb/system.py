"""Platform integration: global hotkey, window focus and auto-paste.

macOS (primary target, Apple Silicon): native AppKit/Quartz via PyObjC. The
hotkey uses NSEvent monitors, whose handlers run on the main thread inside
Tk's Cocoa event loop (pynput's background-thread listener is unstable next
to a Tk GUI on recent macOS releases).
Windows / Linux: pynput + Win32 focus helpers.
"""
from __future__ import annotations

import sys
from typing import Callable

from mydb.hotkey import HotkeyListener, parse_hotkey

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# NSEventModifierFlag* values
_MAC_FLAGS = {"shift": 1 << 17, "ctrl": 1 << 18, "alt": 1 << 19, "cmd": 1 << 20}
_NSEventMaskKeyDown = 1 << 10


# ------------------------------------------------------------------ hotkey
class MacHotkey:
    def __init__(self, spec: str, callback: Callable[[], None]):
        self.mods, self.key = parse_hotkey(spec)
        self.callback = callback
        self._monitors = []

    def _matches(self, event) -> bool:
        flags = int(event.modifierFlags())
        down = {name for name, bit in _MAC_FLAGS.items() if flags & bit}
        chars = (event.charactersIgnoringModifiers() or "").lower()
        return down == set(self.mods) and chars == self.key

    def start(self) -> None:
        from AppKit import NSEvent

        def on_global(event):  # other apps are frontmost
            try:
                if self._matches(event):
                    self.callback()
            except Exception:
                pass

        def on_local(event):  # myDB itself is frontmost
            try:
                if self._matches(event):
                    self.callback()
                    return None  # swallow it
            except Exception:
                pass
            return event

        self._monitors = [
            NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(_NSEventMaskKeyDown, on_global),
            NSEvent.addLocalMonitorForEventsMatchingMask_handler_(_NSEventMaskKeyDown, on_local),
        ]

    def stop(self) -> None:
        from AppKit import NSEvent
        for m in self._monitors:
            if m is not None:
                NSEvent.removeMonitor_(m)
        self._monitors = []


def accessibility_trusted(prompt: bool = True) -> bool | None:
    """macOS: True/False whether we may watch keys / send ⌘V. None = unknown."""
    if not IS_MAC:
        return True
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: prompt}))
    except Exception:
        return None


def make_hotkey(spec: str, callback: Callable[[], None]):
    return MacHotkey(spec, callback) if IS_MAC else HotkeyListener(spec, callback)


# ------------------------------------------------------------------ focus
def setup_process() -> None:
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def remember_frontmost():
    """Return a token for the app/window the user is currently working in."""
    try:
        if IS_MAC:
            from AppKit import NSWorkspace
            return NSWorkspace.sharedWorkspace().frontmostApplication()
        if IS_WIN:
            import ctypes
            return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        pass
    return None


def bring_to_front(win) -> None:
    """Make our Tk window the active one, even when triggered from the background."""
    try:
        if IS_MAC:
            from AppKit import NSApplication
            app = NSApplication.sharedApplication()
            if hasattr(app, "activate"):  # macOS 14+
                app.activate()
            app.activateIgnoringOtherApps_(True)
        elif IS_WIN:
            _win_activate(int(win.wm_frame(), 16))
    except Exception:
        pass
    win.lift()
    win.focus_force()


def restore_frontmost(token) -> None:
    if token is None:
        return
    try:
        if IS_MAC:
            token.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
        elif IS_WIN:
            _win_activate(token)
    except Exception:
        pass


def _win_activate(hwnd: int) -> None:
    import ctypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    fg_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    me = kernel32.GetCurrentThreadId()
    attached = fg_thread and fg_thread != me and user32.AttachThreadInput(fg_thread, me, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(fg_thread, me, False)


# ------------------------------------------------------------------ paste
def send_paste() -> None:
    """Simulate ⌘V (macOS) / Ctrl+V (Windows, Linux) in the frontmost app."""
    if IS_MAC:
        from Quartz import (CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags,
                            kCGEventFlagMaskCommand, kCGHIDEventTap)
        for is_down in (True, False):
            ev = CGEventCreateKeyboardEvent(None, 9, is_down)  # 9 = kVK_ANSI_V
            CGEventSetFlags(ev, kCGEventFlagMaskCommand)
            CGEventPost(kCGHIDEventTap, ev)
        return
    from pynput.keyboard import Controller, Key
    kb = Controller()
    with kb.pressed(Key.ctrl):
        kb.press("v")
        kb.release("v")
