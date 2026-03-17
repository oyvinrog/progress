# ActionDraw

### Your whole plan. One canvas.

<p align="center">
  <img src="https://github.com/oyvinrog/progress/blob/master/assets/img1.png?raw=1" alt="ActionDraw — visual planning canvas" width="700">
</p>

Diagrams, tasks, notes, reminders, priorities, and encrypted storage — in a single desktop app you install with one command.

```bash
pip install actiondraw
```

<p align="center">
  <img src="https://github.com/oyvinrog/progress/blob/master/assets/img2.png?raw=1" alt="ActionDraw — encrypted storage" width="700">
</p>

## What you get

- **Visual task diagrams** — drag boxes, databases, servers, clouds, and sticky notes onto an infinite canvas
- **Live connections** — draw arrows between nodes with drag-and-drop; arrowheads and previews update in real time
- **Markdown notes** — click any node to open a rich markdown editor
- **Time tracking & reminders** — built-in scheduling so nothing slips
- **Priority scoring** — rank tasks by impact and effort with an integrated priority plot
- **Obstacle & wish planning** — dedicated shapes for blockers and goals
- **Free drawing** — sketch and annotate directly on the canvas
- **Paste images** — drop external graphics right onto the diagram
- **Encrypted storage** — your data is protected with Argon2id key derivation, with optional YubiKey challenge-response

## Quick start

```bash
pip install actiondraw    # Install
actiondraw                # Launch the canvas
priorityplot              # Launch standalone priority plot
```

Configure `ntfy` in the app under `Tools > Notification Settings...`. Environment variables `PROGRESS_NTFY_TOPIC`, `PROGRESS_NTFY_SERVER`, and `PROGRESS_NTFY_TOKEN` still work as a fallback.

## Requirements

- Python 3.8+
- PySide6 >= 6.6

## Links

- [Source on GitHub](https://github.com/oyvinrog/progress)
- [Report issues](https://github.com/oyvinrog/progress/issues)
- MIT License
