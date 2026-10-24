"""Floating always-on-top native window. Closing it (red button) returns, and the app then quits."""
import webview


def run_window(url: str) -> None:
    """Block on the main thread until the window is closed. Native frame/traffic lights, stays in the Dock."""
    webview.create_window("Pinoqio", url, width=420, height=720, on_top=True, resizable=True)
    webview.start()
