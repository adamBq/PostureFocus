import time
import math
import cv2
import mediapipe as mp

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from .config import (
    PREVIEW_SIZE,
    NECK_THRESHOLD,
    SHOULDER_THRESHOLD,
    NECK_VERT_THRESHOLD,
    BAD_POSTURE_OPACITY,
    THEME_ACCENT,
    THEME_DANGER,
    THEME_SUCCESS,
)
from .paths import resolve_model_path
from .drawing import draw_pose_skeleton_rgb


class PostureThread(QThread):
    blur_signal = pyqtSignal(float)
    debug_frame_signal = pyqtSignal(QImage)
    status_signal = pyqtSignal(str, str)

    def __init__(self, camera_index: int = 0):
        super().__init__()
        self._camera_index = camera_index
        self._running = False

        # calibration values
        self.calibrated_neck_dist = None
        self.calibrated_shoulder_width = None
        self.calibrated_neck_vert_dist = None

        # current live values
        self.current_neck_dist = 0.0
        self.current_shoulder_width = 0.0
        self.current_neck_vert_dist = 0.0

        # PoseLandmarker setup
        model_path = resolve_model_path()

        BaseOptions = mp.tasks.BaseOptions
        PoseLandmarker = mp.tasks.vision.PoseLandmarker
        PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode

        self._landmarker = PoseLandmarker.create_from_options(
            PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_segmentation_masks=False,
            )
        )

    def stop(self):
        self._running = False

    def calibrate(self):
        self.calibrated_neck_dist = self.current_neck_dist
        self.calibrated_shoulder_width = self.current_shoulder_width
        self.calibrated_neck_vert_dist = self.current_neck_vert_dist

    @staticmethod
    def _dist3(p1, p2) -> float:
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

    @staticmethod
    def _dist2(p1, p2) -> float:
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

    def run(self):
        cap = cv2.VideoCapture(self._camera_index)
        self._running = True
        start_t = time.monotonic()

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    continue

                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
                timestamp_ms = int((time.monotonic() - start_t) * 1000)

                result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

                opacity = 0.0
                status_msg = "Waiting..."
                status_color = "#7f8c8d"

                if result.pose_world_landmarks and len(result.pose_world_landmarks) > 0:
                    world = result.pose_world_landmarks[0]

                    nose = world[0]
                    l_shoulder = world[11]
                    r_shoulder = world[12]

                    # midpoint between shoulders
                    class P: pass
                    midpoint = P()
                    midpoint.x = (l_shoulder.x + r_shoulder.x) / 2
                    midpoint.y = (l_shoulder.y + r_shoulder.y) / 2
                    midpoint.z = (l_shoulder.z + r_shoulder.z) / 2

                    self.current_neck_dist = self._dist3(nose, midpoint)
                    self.current_neck_vert_dist = self._dist2(nose, midpoint)
                    self.current_shoulder_width = self._dist3(l_shoulder, r_shoulder)

                    if (self.calibrated_neck_dist and self.calibrated_shoulder_width and self.calibrated_neck_vert_dist):
                        bad_neck = (
                            self.current_neck_dist < (self.calibrated_neck_dist * NECK_THRESHOLD)
                            or self.current_neck_dist > (self.calibrated_neck_dist * (1 + NECK_THRESHOLD))
                        )
                        bad_shoulders = (
                            self.current_shoulder_width < (self.calibrated_shoulder_width * SHOULDER_THRESHOLD)
                        )
                        bad_neck_vert = (
                            self.current_neck_vert_dist < (self.calibrated_neck_vert_dist * NECK_VERT_THRESHOLD)
                        )

                        if bad_neck or bad_shoulders or bad_neck_vert:
                            opacity = BAD_POSTURE_OPACITY
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
                else:
                    opacity = 0.0
                    status_msg = "No pose detected"
                    status_color = "#7f8c8d"

                self.blur_signal.emit(opacity)
                self.status_signal.emit(status_msg, status_color)

                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    draw_pose_skeleton_rgb(image_rgb, result.pose_landmarks[0])

                # crop square + resize for preview
                h, w, _ = image_rgb.shape
                dim = min(h, w)
                start_x = (w - dim) // 2
                start_y = (h - dim) // 2
                cropped = image_rgb[start_y:start_y + dim, start_x:start_x + dim]
                cropped = cv2.resize(cropped, (PREVIEW_SIZE, PREVIEW_SIZE))

                ch = cropped.shape[2]
                qt_image = QImage(
                    cropped.data,
                    PREVIEW_SIZE,
                    PREVIEW_SIZE,
                    ch * PREVIEW_SIZE,
                    QImage.Format.Format_RGB888,
                )
                self.debug_frame_signal.emit(qt_image)

        finally:
            cap.release()
            try:
                self._landmarker.close()
            except Exception:
                pass
