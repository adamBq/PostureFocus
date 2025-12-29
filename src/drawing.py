import cv2

POSE_CONNECTIONS = [
    (11, 12), (11, 23), (12, 24), (23, 24),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (23, 25), (25, 27),
    (24, 26), (26, 28),
    (0, 11), (0, 12),
]

def draw_pose_skeleton_rgb(image_rgb, normalized_landmarks, connections=POSE_CONNECTIONS) -> None:
    if not normalized_landmarks:
        return

    h, w, _ = image_rgb.shape

    def to_px(lm):
        x = int(max(0.0, min(1.0, float(lm.x))) * w)
        y = int(max(0.0, min(1.0, float(lm.y))) * h)
        return x, y

    for a, b in connections:
        if a >= len(normalized_landmarks) or b >= len(normalized_landmarks):
            continue
        x1, y1 = to_px(normalized_landmarks[a])
        x2, y2 = to_px(normalized_landmarks[b])
        cv2.line(image_rgb, (x1, y1), (x2, y2), (255, 255, 255), 2)

    for i in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]:
        if i >= len(normalized_landmarks):
            continue
        x, y = to_px(normalized_landmarks[i])
        cv2.circle(image_rgb, (x, y), 4, (255, 255, 255), -1)
