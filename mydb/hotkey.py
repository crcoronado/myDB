"""System-wide hotkey listener (Windows / macOS / Linux-X11) built on pynput.

pynput's own GlobalHotKeys can miss Ctrl+letter combos on Windows because the
reported character becomes a control code (Ctrl+S -> '\\x13'), so we track the
modifiers ourselves and resolve the letter from the virtual-key code.
"""
from __future__ import annotations

import sys
from typing import Callable

MODIFIER_NAMES = {"ctrl", "shift", "alt", "cmd"}


def parse_hotkey(spec: str) -> tuple[frozenset[str], str]:
    """'<ctrl>+<shift>+s' -> ({'ctrl','shift'}, 's')."""
    mods, key = set(), ""
    for part in spec.lower().split("+"):
        part = part.strip().strip("<>")
        if part in ("control",):
            part = "ctrl"
        if part in ("win", "super", "command"):
            part = "cmd"
        if part in MODIFIER_NAMES:
            mods.add(part)
        elif part:
            key = part
    if not key:
        raise ValueError(f"Hotkey '{spec}' has no main key")
    return frozenset(mods), key


def pretty_hotkey(spec: str) -> str:
    mods, key = parse_hotkey(spec)
    order = ["ctrl", "alt", "shift", "cmd"]
    names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Win" if sys.platform == "win32" else "Cmd"}
    return "+".join([names[m] for m in order if m in mods] + [key.upper()])


def key_to_name(key) -> str | None:
    """Turn a pynput key into a short lowercase name ('s', 'f5', 'ctrl', ...)."""
    from pynput.keyboard import Key, KeyCode

    if isinstance(key, Key):
        name = key.name  # e.g. ctrl_l, shift_r, f5, space
        for mod in MODIFIER_NAMES:
            if name == mod or name.startswith(mod + "_"):
                return mod
        if name.startswith("alt"):
            return "alt"
        return name
    if isinstance(key, KeyCode):
        vk = getattr(key, "vk", None)
        if sys.platform == "win32" and vk is not None:
            if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:  # A-Z, 0-9
                return chr(vk).lower()
        ch = key.char
        if ch:
            if len(ch) == 1 and ord(ch) < 32:  # Ctrl+letter control code
                return chr(ord(ch) + 96)
            return ch.lower()
        if vk is not None and 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
    return None


class HotkeyListener:
    def __init__(self, spec: str, callback: Callable[[], None]):
        self.mods, self.key = parse_hotkey(spec)
        self.callback = callback
        self.down: set[str] = set()
        self._listener = None

    def start(self) -> None:
        from pynput import keyboard

        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key) -> None:
        name = key_to_name(key)
        if not name:
            return
        if name in MODIFIER_NAMES:
            self.down.add(name)
            return
        if name == self.key and self.down == set(self.mods):
            self.callback()

    def _on_release(self, key) -> None:
        name = key_to_name(key)
        if name in MODIFIER_NAMES:
            self.down.discard(name)
