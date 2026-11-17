"""macOS menu-bar mode: a 🔍 icon in the menu bar, no Dock icon, no main window.

Menu: Search… · last action · Settings… · Quit. On other platforms (or if
PyObjC is missing) myDB falls back to its normal small window.
"""
from __future__ import annotations

import argparse

from mydb import system
from mydb.hotkey import pretty_hotkey

ACCESSIBILITY_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
_TARGET_CLASS = None


def _target_class():
    """Objective-C class that receives menu clicks (defined once per process)."""
    global _TARGET_CLASS
    if _TARGET_CLASS is None:
        from Foundation import NSObject

        class MyDBMenuTarget(NSObject):
            def search_(self, sender):
                self.app.root.after(0, self.app.open_search)

            def settings_(self, sender):
                def go():
                    self.app.open_settings()
                    system.bring_to_front(self.app.settings)
                self.app.root.after(0, go)

            def accessibility_(self, sender):
                from AppKit import NSURL, NSWorkspace
                NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(ACCESSIBILITY_URL))

            def quit_(self, sender):
                self.app.root.after(0, self.app.quit)

            def menuWillOpen_(self, menu):  # refresh texts every time the menu opens
                self.bar.refresh()

        _TARGET_CLASS = MyDBMenuTarget
    return _TARGET_CLASS


class MenuBar:
    def __init__(self, app):
        from AppKit import (NSApplication, NSImage, NSMenu, NSMenuItem, NSStatusBar,
                            NSVariableStatusItemLength)
        self.app = app
        self.target = _target_class().alloc().init()
        self.target.app = app
        self.target.bar = self

        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        button = self.item.button()
        image = None
        if hasattr(NSImage, "imageWithSystemSymbolName_accessibilityDescription_"):
            image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("magnifyingglass.circle", "myDB")
        if image is not None:
            image.setTemplate_(True)  # adapts to light / dark menu bar
            button.setImage_(image)
        else:
            button.setTitle_("myDB")
        button.setToolTip_("myDB quick search")

        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        menu.setDelegate_(self.target)

        def add(title, action=None, key=""):
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
            if action:
                mi.setTarget_(self.target)
            else:
                mi.setEnabled_(False)
            menu.addItem_(mi)
            return mi

        self.search_item = add("Search…", "search:")
        menu.addItem_(NSMenuItem.separatorItem())
        self.status_item = add("Ready")
        self.warn_item = add("⚠ Allow Accessibility so the hotkey works…", "accessibility:")
        menu.addItem_(NSMenuItem.separatorItem())
        add("Settings…", "settings:", ",")
        add("Quit myDB", "quit:", "q")
        self.item.setMenu_(menu)
        self.menu = menu

        # Show feedback in the menu bar (the main window is hidden in this mode).
        original_set_status = app.set_status

        def set_status(text: str) -> None:
            original_set_status(text)
            self.status_item.setTitle_(text[:70])
            self.flash("✓")

        app.set_status = set_status

        NSApplication.sharedApplication().setActivationPolicy_(1)  # Accessory: no Dock icon
        app.root.withdraw()
        self.refresh()

    def refresh(self) -> None:
        try:
            hk = pretty_hotkey(self.app.cfg.get("hotkey", "<ctrl>+<shift>+s"))
        except ValueError:
            hk = "?"
        self.search_item.setTitle_(f"Search…   ({hk})")
        trusted = system.accessibility_trusted(prompt=False)
        self.warn_item.setHidden_(trusted is not False)

    def flash(self, text: str, ms: int = 1500) -> None:
        button = self.item.button()
        button.setTitle_(" " + text)
        self.app.root.after(ms, lambda: button.setTitle_(""))


def install(app) -> MenuBar | None:
    """Switch the running app to menu-bar mode. Returns None if not possible."""
    if not system.IS_MAC:
        return None
    try:
        bar = MenuBar(app)
    except Exception as exc:  # PyObjC missing or AppKit error -> keep the window
        app.set_status(f"Menu bar unavailable ({exc}); using the window instead.")
        return None
    app.menubar = bar  # keep references alive
    return bar


def main() -> None:
    from mydb.app import App

    ap = argparse.ArgumentParser(description="myDB quick CSV search (menu-bar app on macOS)")
    ap.add_argument("--minimized", action="store_true", help="start minimised (window mode only)")
    ap.add_argument("--search", action="store_true", help="open the search popup immediately")
    ap.add_argument("--window", action="store_true", help="use the classic window instead of the menu bar")
    args = ap.parse_args()
    app = App(start_minimized=args.minimized)
    if not args.window:
        install(app)
    if args.search:
        app.root.after(300, app.open_search)
    app.run()


if __name__ == "__main__":
    main()
