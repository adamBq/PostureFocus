import sys
import os
import time
import cv2
import mediapipe as mp
import math
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QSize
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QFont, QIcon, QBrush
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QHBoxLayout, QFrame, QGraphicsDropShadowEffect
)

# --- CONFIGURATION ---
THEME_BG = "#1e1e1e"
THEME_ACCENT = "#3498db"     # Blue
THEME_DANGER = "#e74c3c"     # Red
THEME_SUCCESS = "#2ecc71"    # Green
THEME_TEXT = "#ecf0f1"
FONT_MAIN = "Helvetica Neue" # Standard Mac Font

# MediaPipe Tasks model path:
# Download a Pose Landmarker .task model and place it next to this script, OR set env var POSE_MODEL_PATH.
DEFAULT_MODEL_FILENAME = "pose_landmarker_heavy.task"
MODEL_PATH = os.environ.get(
    "POSE_MODEL_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULT_MODEL_FILENAME)
)

POSE_CONNECTIONS = [
    # Torso
    (11, 12), (11, 23), (12, 24), (23, 24),
    # Left arm
    (11, 13), (13, 15),
    # Right arm
    (12, 14), (14, 16),
    # Left leg
    (23, 25), (25, 27),
    # Right leg
    (24, 26), (26, 28),
    # Head-ish
    (0, 11), (0, 12),
]


def draw_pose_skeleton_rgb(image_rgb, normalized_landmarks, connections=POSE_CONNECTIONS):
    """
    image_rgb: np.ndarray (H,W,3) RGB
    normalized_landmarks: list of landmarks with .x .y in [0,1] (PoseLandmarker output)
    """
    if not normalized_landmarks:
        return

    h, w, _ = image_rgb.shape

    def to_px(lm):
        x = int(max(0.0, min(1.0, float(lm.x))) * w)
        y = int(max(0.0, min(1.0, float(lm.y))) * h)
        return x, y

    # Draw connections
    for a, b in connections:
        if a >= len(normalized_landmarks) or b >= len(normalized_landmarks):
            continue
        x1, y1 = to_px(normalized_landmarks[a])
        x2, y2 = to_px(normalized_landmarks[b])
        cv2.line(image_rgb, (x1, y1), (x2, y2), (255, 255, 255), 2)

    # Draw keypoints
    for i in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]:
        if i >= len(normalized_landmarks):
            continue
        x, y = to_px(normalized_landmarks[i])
        cv2.circle(image_rgb, (x, y), 4, (255, 255, 255), -1)

# --- 1. AI WORKER THREAD (Uses NEW MediaPipe PoseLandmarker Tasks API) ---

class PostureThread(QThread):
    blur_signal = pyqtSignal(float)
    debug_frame_signal = pyqtSignal(QImage)
    status_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.running = False

        # --- CALIBRATION STORAGE ---
        self.calibrated_neck_dist = None
        self.calibrated_shoulder_width = None
        self.calibrated_neck_vert_dist = None

        # --- LIVE SNAPSHOTS (For the Calibrate Button) ---
        self.current_neck_dist = 0.0
        self.current_shoulder_width = 0.0
        self.current_neck_vert_dist = 0.0

        # --- SENSITIVITY ---
        self.NECK_THRESHOLD = 0.95
        self.SHOULDER_THRESHOLD = 0.92
        self.NECK_VERT_THRESHOLD = 0.85

        # Drawing helpers (still fine to use for rendering)
        # self.mp_drawing = mp.solutions.drawing_utils
        # self.mp_pose = mp.solutions.pose

        # NEW Tasks API imports
        # (Using mp.tasks.* is the recommended way per official docs)
        BaseOptions = mp.tasks.BaseOptions
        PoseLandmarker = mp.tasks.vision.PoseLandmarker
        PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Pose model not found at:\n  {MODEL_PATH}\n\n"
                f"Place '{DEFAULT_MODEL_FILENAME}' next to this script, or set POSE_MODEL_PATH."
            )

        # Create a landmarker instance in VIDEO mode so we can call detect_for_video(frame, timestamp_ms)
        self._landmarker = PoseLandmarker.create_from_options(
            PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=MODEL_PATH),
                running_mode=VisionRunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_segmentation_masks=False
            )
        )

        # # For converting to the drawing proto
        # from mediapipe.framework.formats import landmark_pb2
        # self._landmark_pb2 = landmark_pb2

    def calculate_3d_distance(self, p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

    def calculate_2d_distance(self, p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

    # def _to_normalized_landmark_list(self, landmarks):
    #     """
    #     Convert Tasks API landmarks (list of objects with x,y,z,visibility,presence)
    #     into MediaPipe NormalizedLandmarkList proto for drawing_utils.draw_landmarks.
    #     """
    #     nl_list = self._landmark_pb2.NormalizedLandmarkList()
    #     for lm in landmarks:
    #         nl_list.landmark.append(
    #             self._landmark_pb2.NormalizedLandmark(
    #                 x=float(lm.x),
    #                 y=float(lm.y),
    #                 z=float(getattr(lm, "z", 0.0)),
    #                 visibility=float(getattr(lm, "visibility", 0.0)),
    #                 presence=float(getattr(lm, "presence", 0.0)),
    #             )
    #         )
    #     return nl_list

    def run(self):
        cap = cv2.VideoCapture(0)
        self.running = True

        start_t = time.monotonic()

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    continue

                # OpenCV -> RGB
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Tasks API requires mp.Image
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

                # Monotonically increasing timestamp (ms)
                timestamp_ms = int((time.monotonic() - start_t) * 1000)

                # NEW: run PoseLandmarker
                result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

                opacity = 0.0
                status_msg = "Waiting..."
                status_color = "#7f8c8d"

                # result.pose_world_landmarks is a list (one entry per detected pose)
                if result.pose_world_landmarks and len(result.pose_world_landmarks) > 0:
                    world_landmarks = result.pose_world_landmarks[0]

                    # --- GET KEYPOINTS (same indices as before) ---
                    nose = world_landmarks[0]
                    l_shoulder = world_landmarks[11]
                    r_shoulder = world_landmarks[12]

                    # --- CALCULATE MIDPOINT ---
                    midpoint = type('Point', (), {})()
                    midpoint.x = (l_shoulder.x + r_shoulder.x) / 2
                    midpoint.y = (l_shoulder.y + r_shoulder.y) / 2
                    midpoint.z = (l_shoulder.z + r_shoulder.z) / 2

                    # --- METRIC 1: NECK LENGTH (3D + 2D proxy) ---
                    self.current_neck_dist = self.calculate_3d_distance(nose, midpoint)
                    self.current_neck_vert_dist = self.calculate_2d_distance(nose, midpoint)

                    # --- METRIC 2: SHOULDER WIDTH (3D) ---
                    self.current_shoulder_width = self.calculate_3d_distance(l_shoulder, r_shoulder)

                    # --- CHECK POSTURE ---
                    if (
                        self.calibrated_neck_dist
                        and self.calibrated_shoulder_width
                        and self.calibrated_neck_vert_dist
                    ):
                        bad_neck = (
                            self.current_neck_dist < (self.calibrated_neck_dist * self.NECK_THRESHOLD)
                            or self.current_neck_dist > (self.calibrated_neck_dist * (1 + self.NECK_THRESHOLD))
                        )
                        bad_shoulders = (
                            self.current_shoulder_width < (self.calibrated_shoulder_width * self.SHOULDER_THRESHOLD)
                        )
                        bad_neck_vert = (
                            self.current_neck_vert_dist < (self.calibrated_neck_vert_dist * self.NECK_VERT_THRESHOLD)
                        )

                        if bad_neck or bad_shoulders or bad_neck_vert:
                            opacity = 0.85
                            status_color = THEME_DANGER

                            if bad_neck and bad_shoulders:
                                status_msg = "⚠️ FULL SLOUCH"
                            elif bad_neck:
                                status_msg = "⚠️ HEAD DROP"
                            elif bad_shoulders:
                                status_msg = "⚠️ ROUNDED SHOULDERS"
                            else:
                                status_msg = "⚠️ POSTURE OFF"
                        else:
                            opacity = 0.0
                            status_msg = "✅ GOOD POSTURE"
                            status_color = THEME_SUCCESS
                    else:
                        status_msg = "Please Calibrate"
                        status_color = THEME_ACCENT

                # Emit Signals
                self.blur_signal.emit(opacity)
                self.status_signal.emit(status_msg, status_color)

                # Draw Debug (Tasks-only)
                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    draw_pose_skeleton_rgb(image_rgb, result.pose_landmarks[0])


                # Crop & Display logic (same as before)
                h, w, _ = image_rgb.shape
                dim = min(h, w)
                start_x = (w - dim) // 2
                start_y = (h - dim) // 2
                cropped = image_rgb[start_y:start_y + dim, start_x:start_x + dim]
                cropped = cv2.resize(cropped, (300, 300))
                h, w, ch = cropped.shape
                qt_image = QImage(cropped.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.debug_frame_signal.emit(qt_image)

        finally:
            cap.release()
            try:
                self._landmarker.close()
            except Exception:
                pass

    def calibrate(self):
        # Capture metrics when user clicks
        self.calibrated_neck_dist = self.current_neck_dist
        self.calibrated_shoulder_width = self.current_shoulder_width
        self.calibrated_neck_vert_dist = self.current_neck_vert_dist


# --- 2. OVERLAY WINDOW (The Blur Effect) ---
class OverlayWindow(QMainWindow):
    def __init__(self, screen):
        super().__init__()
        self.setScreen(screen)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        # self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)

        self.setGeometry(screen.geometry())
        self.current_opacity = 0.0

        QTimer.singleShot(100, self.set_macos_window_level)

    def set_macos_window_level(self):
        """Set macOS-specific window level to float above all apps"""
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
            print(f"Warning: Could not set macOS window level: {e}")

    def paintEvent(self, event):
        if self.current_opacity > 0:
            painter = QPainter(self)
            color = QColor(10, 5, 5)
            color.setAlphaF(self.current_opacity)
            painter.fillRect(self.rect(), color)

    def update_opacity(self, value):
        self.current_opacity = value
        self.repaint()


class OverlayManager:
    def __init__(self):
        self.overlays = []
        screens = QApplication.screens()

        for screen in screens:
            window = OverlayWindow(screen)
            window.show()
            self.overlays.append(window)

    def update_all_opacity(self, value):
        for window in self.overlays:
            window.update_opacity(value)


# --- 3. UI COMPONENTS ---
class ModernButton(QPushButton):
    def __init__(self, text, color=THEME_ACCENT):
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
            QPushButton:hover {{
                background-color: {color}99;
            }}
            QPushButton:pressed {{
                background-color: {color}77;
            }}
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

    def update_status(self, text, color_hex):
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


# --- 4. MAIN CONTROL PANEL ---
class ControlPanel(QWidget):
    def __init__(self, thread, overlay):
        super().__init__()
        self.thread = thread
        self.overlay = overlay

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
        self.thread.blur_signal.connect(self.overlay.update_opacity)

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


# --- RUN ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    font = QFont(FONT_MAIN)
    app.setFont(font)

    thread = PostureThread()

    overlay_manager = OverlayManager()
    thread.blur_signal.connect(overlay_manager.update_all_opacity)

    window = ControlPanel(thread, overlay_manager.overlays[0])
    window.show()

    sys.exit(app.exec())
