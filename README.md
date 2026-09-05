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

- **Global mindmap** — arrange thoughts and notes around every project tab; click a tab node to open it. The map is saved inside the encrypted project file.
- **Visual task diagrams** — drag boxes, databases, servers, clouds, and sticky notes onto an infinite canvas
- **Live connections** — draw arrows between nodes with drag-and-drop; arrowheads and previews update in real time
- **Markdown notes** — click any node to open a rich markdown editor
- **Time tracking & reminders** — built-in scheduling so nothing slips
- **Priority scoring** — rank tasks by impact and effort with an integrated priority plot
- **Obstacle & wish planning** — dedicated shapes for blockers and goals
- **Free drawing** — sketch and annotate directly on the canvas
- **Action Paint** — sketch a scene, place and reorder numbered actions, then add them to the diagram as a connected task chain
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

## Project mindmap

Choose **Mindmap** above the sidebar tabs. Drag nodes onto another node to nest
them, or onto its top/bottom edge to reorder. Right-click a tab node to add
thoughts or edit notes; a normal click opens the tab. Use Alt+Left to return.

In the map, Tab adds a child, Enter adds a sibling, F2 edits, Space folds,
and Ctrl+Z / Ctrl+Y undo and redo. Use the mouse wheel to zoom and drag the
background to pan. Deleting a project tab keeps its map node as a thought.

The mindmap reuses the MIT-licensed [PyPlane](https://github.com/oyvinrog/pyplane)
core, bundled with its license and source revision.
