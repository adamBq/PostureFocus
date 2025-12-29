import sys
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from src.config import FONT_MAIN
from src.posture_thread import PostureThread
from src.overlay import OverlayManager
from src.ui import ControlPanel


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont(FONT_MAIN))

    thread = PostureThread(camera_index=0)

    overlay_manager = OverlayManager()
    thread.blur_signal.connect(overlay_manager.update_all_opacity)

    window = ControlPanel(thread)
    window.show()

    code = app.exec()

    try:
        thread.stop()
        thread.wait(500)
    except Exception:
        pass

    sys.exit(code)


if __name__ == "__main__":
    main()
