from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsDropShadowEffect, QPushButton

from .config import THEME_BG, THEME_ACCENT, THEME_SUCCESS, THEME_TEXT, FONT_MAIN

class ModernButton(QPushButton):
    def __init__(self, text: str, color: str = THEME_ACCENT):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border-radius: 8px;
                padding: 12px;
                font-family: '{FONT_MAIN}';
                font-weight: bold;
                font-size: 14px;
                border: none;
            }}
            QPushButton:hover {{ background-color: {color}99; }}
            QPushButton:pressed {{ background-color: {color}77; }}
            QPushButton:disabled {{
                background-color: #333333;
                color: #555555;
            }}
        """)

class StatusPill(QLabel):
    def __init__(self):
        super().__init__("Ready")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: #333;
                color: {THEME_TEXT};
                border-radius: 15px;
                padding: 5px 15px;
                font-family: '{FONT_MAIN}';
                font-weight: 600;
                font-size: 12px;
            }}
        """)

    def update_status(self, text: str, color_hex: str):
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color_hex}33;
                color: {color_hex};
                border: 1px solid {color_hex};
                border-radius: 15px;
                padding: 5px 15px;
                font-family: '{FONT_MAIN}';
                font-weight: 600;
            }}
        """)

class ControlPanel(QWidget):
    def __init__(self, thread):
        super().__init__()
        self.thread = thread

        self.setWindowTitle("PostureFocus")
        self.setFixedSize(360, 500)
        self.setStyleSheet(f"background-color: {THEME_BG};")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("PostureFocus")
        title.setStyleSheet(f"color: white; font-size: 24px; font-weight: bold; font-family: '{FONT_MAIN}';")
        main_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.cam_frame = QLabel()
        self.cam_frame.setFixedSize(300, 300)
        self.cam_frame.setStyleSheet("""
            background-color: #000;
            border-radius: 20px;
            border: 2px solid #333;
        """)
        self.cam_frame.setScaledContents(True)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 5)
        self.cam_frame.setGraphicsEffect(shadow)
        main_layout.addWidget(self.cam_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_pill = StatusPill()
        main_layout.addWidget(self.status_pill, alignment=Qt.AlignmentFlag.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_start = ModernButton("Start Camera", THEME_ACCENT)
        self.btn_start.clicked.connect(self.start_camera)

        self.btn_calibrate = ModernButton("Calibrate", THEME_SUCCESS)
        self.btn_calibrate.clicked.connect(self.calibrate)
        self.btn_calibrate.setEnabled(False)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_calibrate)
        main_layout.addLayout(btn_layout)

        footer = QLabel("Sit straight, then click Calibrate.")
        footer.setStyleSheet("color: #666; font-size: 11px; margin-top: 5px;")
        main_layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(main_layout)

        self.thread.debug_frame_signal.connect(self.update_image)
        self.thread.status_signal.connect(self.status_pill.update_status)

    def start_camera(self):
        self.thread.start()
        self.btn_start.setText("Running...")
        self.btn_start.setEnabled(False)
        self.btn_calibrate.setEnabled(True)

    def calibrate(self):
        self.thread.calibrate()
        self.btn_calibrate.setText("Calibrated!")
        QTimer.singleShot(1000, lambda: self.btn_calibrate.setText("Recalibrate"))

    def update_image(self, qt_image):
        self.cam_frame.setPixmap(QPixmap.fromImage(qt_image))
