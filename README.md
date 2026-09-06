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
thoughts or edit notes; a normal click opens the tab. Ctrl+click toggles nodes in the selection without opening tabs; Shift+click
selects a range, and Shift+arrow keys extend the selection. Use Alt+Left to return.

In the map, arrow keys select nearby visible nodes and keep them on screen.
Tab adds a child to the selected node (including tabs), Ctrl+Enter opens the
selected tab, Enter adds a sibling, F2 edits, Space folds, F4 toggles completion,
and Ctrl+Z / Ctrl+Y undo and redo. Use the mouse wheel to zoom and drag the
background to pan. Deleting a project tab keeps its map node as a thought.

Tabs with child nodes open in a mindmap showing their branch. Use **Canvas**
to return to the tab's canvas and **Mindmap** to view or start its branch.
The sidebar **Mindmap** opens the full project map. Both views edit the same
nodes, so changes and undo/redo are shared. The tab view's root stays in place;
open nested tab nodes to view their branches and use Alt+Left to return.

Task nodes use three blue shades and one, two, or three filled bars to show
lower, middle, or higher relative priority from the priority plot's calculated
score. Levels compare all included project tabs, so opening or folding a branch
does not change the scale. Tied scores share a level; a single task or all-equal
scores use the middle level. Hover over a task for its score. Notes and tabs
excluded from the priority plot have no priority indicator.

Use **Complete** in the toolbar or right-click menu, or press **F4**, to mark
selected nodes with a ✓. If all selected nodes are already complete, this clears
their marks. Descendants and canvas tasks are unaffected. Marks are saved with
the project.

Select a single node and choose **Reminder**, or right-click it to set, update,
or clear a reminder. Every node supports its own reminder, including tab nodes
and the project root. Use the same date/time presets and optional notifications
as canvas tasks. An orange bell and date appear beneath the node title.

**Waiting Reminders** stays visible above both the canvas and mindmap. Use
**Open Node** to reveal a reminder's node, including inside folded branches.
Completing or deleting a node cancels its reminder; undo restores it. Reminders
that have already fired stay cleared through undo/redo; use **Renew** in the due
alert to schedule another one.

The mindmap reuses the MIT-licensed [PyPlane](https://github.com/oyvinrog/pyplane)
core, bundled with its license and source revision.

To move several branches, select them and press Ctrl+X, select a destination,
then press Ctrl+V. Cut branches stay dimmed in place until pasted; Escape
cancels the cut. Clicking a tab while a cut is pending selects it as the
destination. The move preserves tab links and descendants and can be undone
with Ctrl+Z. Cut selections are local to the current project.
