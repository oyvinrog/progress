# Progress List

A progress tracking task list with time estimation using PySide6 + QML.

## Features

- ✓ Tasks with checkboxes to mark completion
- ✓ Automatic time tracking for active tasks
- ✓ Estimated completion times based on historical average
- ✓ Break down tasks into subtasks
- ✓ Add new tasks dynamically
- ✓ Burndown charts to visualize progress

## Installation

```bash
pip install progress-list
```

## Usage

```python
from progress_list import ProgressListApp

# Run the application
app = ProgressListApp()
app.run()
```

Or run directly from the command line:

```bash
python -m progress_list
```

## Requirements

- Python 3.8+
- PySide6 >= 6.6
- matplotlib >= 3.7.0

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
