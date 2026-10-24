"""Floating always-on-top native window. Closing it (red button) returns, and the app then quits."""
from pathlib import Path

import webview

ICON = Path(__file__).parent / "ui" / "static" / "logo-512.png"


def _set_dock_icon() -> None:
    """pywebview's icon= is GTK/Qt only; on macOS set the Dock icon through AppKit (pyobjc ships with pywebview)."""
    try:
        from AppKit import NSApplication, NSImage
        NSApplication.sharedApplication().setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(str(ICON)))
    except Exception as e:  # cosmetic: never block the window
        print(f"dock icon skipped: {e}")


def run_window(url: str) -> None:
    """Block on the main thread until the window is closed. Native frame/traffic lights, stays in the Dock."""
    webview.create_window("Pinoqio", url, width=420, height=720, on_top=True, resizable=True)
    _set_dock_icon()
    webview.start()
