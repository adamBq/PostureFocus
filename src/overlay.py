from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QMainWindow, QApplication

class OverlayWindow(QMainWindow):
    def __init__(self, screen):
        super().__init__()
        self.setScreen(screen)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self.setGeometry(screen.geometry())
        self.current_opacity = 0.0

        QTimer.singleShot(100, self._set_macos_window_level)

    def _set_macos_window_level(self):
        try:
            import objc
            from Cocoa import NSScreenSaverWindowLevel, NSWindowCollectionBehaviorCanJoinAllSpaces
            from ctypes import c_void_p

            win_id = self.winId()
            if win_id:
                nsview = objc.objc_object(c_void_p=int(win_id))
                nswindow = nsview.window()
                nswindow.setLevel_(NSScreenSaverWindowLevel)
                nswindow.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)
                nswindow.setHidesOnDeactivate_(False)
                nswindow.setIgnoresMouseEvents_(True)
        except Exception as e:
            # safe fallback: overlay still works without this
            print(f"Warning: Could not set macOS window level: {e}")

    def paintEvent(self, event):
        if self.current_opacity > 0:
            painter = QPainter(self)
            color = QColor(10, 5, 5)
            color.setAlphaF(self.current_opacity)
            painter.fillRect(self.rect(), color)

    def update_opacity(self, value: float):
        self.current_opacity = float(value)
        self.repaint()

class OverlayManager:
    def __init__(self):
        self.overlays = []
        for screen in QApplication.screens():
            w = OverlayWindow(screen)
            w.show()
            self.overlays.append(w)

    def update_all_opacity(self, value: float):
        for w in self.overlays:
            w.update_opacity(value)
