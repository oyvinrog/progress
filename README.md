# ActionDraw

A diagramming module built with PySide6 and QML for creating system diagrams, flowcharts, and visual documentation.

![Screenshot](assets/screenshot.png)

## Features

- Preset shapes for boxes, databases, servers, clouds, notes, obstacles, and wishes
- Snap-to-grid toggle with optional grid overlay for tidy layouts
- Smooth zoom controls via toolbar, mouse wheel (Ctrl+Scroll), or touchpad pinch
- Drag-and-drop connections with live previews and arrowheads
- Quick resizing gestures (pinch) that respect to grid spacing
- Inline editing for labels
- Task integration with task management capabilities
- Free drawing mode for sketches and annotations
- Image paste functionality for adding external graphics

## Installation

Install from the latest release:

```bash
pip install git+https://github.com/oyvinrog/progress.git
```

Or install from the repo:

```bash
pip install .
```

## Usage

After installation, run from anywhere:

```bash
actiondraw       # Diagramming canvas
```

For local development (from the repo directory):

```bash
python -m actiondraw
```

Key capabilities:

- Preset shapes for boxes, databases, servers, clouds, and sticky notes
- Snap-to-grid toggle with optional grid overlay for tidy layouts
- Smooth zoom controls via toolbar, mouse wheel (Ctrl+Scroll), or touchpad pinch
- Drag-and-drop connections with live previews and arrowheads
- Quick resizing gestures (pinch) that respect the grid spacing
- Inline editing for labels plus task integration with the main progress list

## Installation


Latest:

```bash
pip install git+https://github.com/oyvinrog/progress.git
```

Latest stable release:

```bash
pip install progress-list
```

Or install from the repo:

```bash
pip install .
```

## Usage

After installation, run from anywhere:

```bash
progress-list    # Main progress tracking app
actiondraw       # Standalone diagramming canvas
```

For local development (from the repo directory):

```bash
python -m actiondraw
```

## Requirements

- Python 3.8+
- PySide6 >= 6.6
- matplotlib >= 3.7.0
- cryptography >= 42.0.0
- argon2-cffi >= 23.1.0

### Optional: YubiKey Support

YubiKey-based encryption mode is optional and not required for normal save/load.
The app uses the `ykman` CLI for challenge-response.

The app detects YubiKey capability at runtime and shows in-app setup guidance
if YubiKey mode is selected while support is unavailable.
If `ykman` is not found, you can still use passphrase-only mode.

Linux setup:

```bash
sudo apt update
sudo apt install -y yubikey-manager pcscd
```

Windows setup (no admin-friendly option):
- Use a portable `ykman.exe` and set `YKMAN_PATH` to that file path before starting the app.
- If `ykman` is on PATH already, no extra env var is required.

Example:

```bash
set YKMAN_PATH=C:\tools\ykman\ykman.exe
```

## Development

### Install development dependencies

```bash
pip install -r requirements-dev.txt
```

### Run tests

```bash
pytest
```

## License

MIT License - see LICENSE file for details.
