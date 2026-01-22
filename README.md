# PostureFocus 🧘‍♂️

A real-time posture monitoring application for macOS that uses AI-powered pose detection to help you maintain good posture while working. When you slouch, the screen blurs to remind you to sit up straight.

![PostureFocus Demo](https://img.shields.io/badge/Platform-macOS-blue) ![Python](https://img.shields.io/badge/Python-3.13+-green)

## Features

- **Real-time Posture Detection**: Uses MediaPipe AI to track your neck and shoulder positions
- **Visual Feedback**: Screen overlay blurs when bad posture is detected
- **Multi-Monitor Support**: Works across all connected displays
- **Customizable Calibration**: Set your ideal posture as the baseline
- **Non-Intrusive**: Overlay works even when the app is in the background
- **Click-Through Interface**: The blur overlay doesn't block your mouse clicks

## How It Works

1. The app uses your webcam to track key body landmarks (nose, shoulders)
2. You calibrate by sitting in your ideal posture (NOTE: The camera must be infront of you, not diagonal)
3. The app continuously monitors three metrics:
   - **Neck distance** (3D) - detects forward head posture
   - **Neck vertical distance** (2D) - detects head dropping
   - **Shoulder width** - detects rounded shoulders
4. When posture degrades beyond thresholds, a red overlay blurs your screen

## Requirements

- **macOS** (tested on Apple Silicon, should work on Intel Macs)
- **Python 3.13+**
- **Webcam** (built-in or external)

## Installation

### 1. Clone or Download

```bash
git clone <your-repo-url>
cd posture-focus
```

### 2. Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Grant Camera Permissions

When you first run the app, macOS will ask for camera permissions. Click **Allow**.

If you accidentally denied it:
1. Go to **System Settings** → **Privacy & Security** → **Camera**
2. Enable access for **Terminal** or **Python**

## Usage

### Running the App

```bash
python3 main.py
```

### Setup Steps

1. **Start Camera**: Click the "Start Camera" button
2. **Position Yourself**: Sit in your ideal posture - back straight, shoulders relaxed
3. **Calibrate**: Click the "Calibrate" button to set this as your baseline
4. **Work Normally**: The app will monitor your posture in the background

### Understanding the Indicators

**Status Messages:**
- ✅ **GOOD POSTURE** (Green) - You're sitting correctly
- ⚠️ **HEAD DROP** (Red) - Your head is tilted down
- ⚠️ **ROUNDED SHOULDERS** (Red) - Your shoulders are hunched forward
- ⚠️ **FULL SLOUCH** (Red) - Multiple posture issues detected
- **Please Calibrate** (Blue) - You need to set your baseline posture

**Screen Overlay:**
- **Clear screen** - Good posture
- **Red blur overlay** - Bad posture detected

## Customization

You can adjust sensitivity thresholds in `main.py`:

```python
class PostureThread(QThread):
    def __init__(self):
        # ...
        self.NECK_THRESHOLD = 0.95        # 5% tolerance for neck movement
        self.SHOULDER_THRESHOLD = 0.92    # 8% tolerance for shoulder width
        self.NECK_VERT_THRESHOLD = 0.85   # 15% tolerance for vertical neck distance
```

**Lower values** = More sensitive (triggers with smaller posture changes)  
**Higher values** = Less sensitive (only triggers with larger changes)

## Troubleshooting

### Camera Not Working

**Issue**: Black screen in the camera preview

**Solutions**:
- Check camera permissions in System Settings
- Ensure no other app is using the camera (Zoom, FaceTime, etc.)
- Restart the application

### Overlay Not Appearing

**Issue**: Screen doesn't blur when slouching

**Solutions**:
- Make sure you've clicked "Calibrate" after starting the camera
- Verify the status pill shows "GOOD POSTURE" when sitting correctly
- Check console for any error messages

### Overlay Not Visible When App Is in Background

**Issue**: Overlay only works when the app window is focused

**Solution**: This should work automatically on macOS. If not, ensure you have `pyobjc-framework-Cocoa` installed:
```bash
pip install pyobjc-framework-Cocoa
```

### False Positives

**Issue**: Overlay triggers too often

**Solution**: Adjust the threshold values (see Customization section) or recalibrate in your typical working position.

## Technical Details

### Architecture

- **PostureThread**: Background thread running MediaPipe pose detection
- **OverlayWindow**: Transparent, click-through window that displays blur effect
- **ControlPanel**: Main GUI for camera preview and controls
- **OverlayManager**: Manages overlays across multiple monitors

### Key Technologies

- **MediaPipe Pose**: Google's ML solution for real-time pose estimation
- **PyQt6**: Cross-platform GUI framework
- **OpenCV**: Computer vision library for camera capture
- **macOS Cocoa**: Native window management for always-on-top behavior

## Known Limitations

- **macOS only** - Uses Cocoa framework for window management
- **Requires good lighting** - Poor lighting affects pose detection accuracy
- **Single person detection** - Designed for one person in frame
- **Camera must be visible** - Works best with laptop or monitor-mounted webcam

## Future Enhancements

- [ ] Work with camera in diagonal position

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use and modify as needed.

## Acknowledgments

- [MediaPipe](https://google.github.io/mediapipe/) - Pose detection framework
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework

---

**Stay healthy, sit straight! 💪**