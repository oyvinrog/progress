"use strict";
const $ = (id) => document.getElementById(id);
const el = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
const button = (text, fn, cls) => {
  const b = el("button", text, cls);
  b.type = "button";
  b.onclick = fn;
  return b;
};
const key = new URLSearchParams(location.hash.slice(1)).get("key");
if (key) sessionStorage.setItem("actiondraw-key", key);
history.replaceState(null, "", location.pathname);
// Scanning a new QR may reuse this tab and only change its fragment.
window.addEventListener("hashchange", () => {
  const nextKey = new URLSearchParams(location.hash.slice(1)).get("key");
  if (nextKey) {
    sessionStorage.setItem("actiondraw-key", nextKey);
    history.replaceState(null, "", location.pathname);
    refresh();
  }
});
let state = null,
  nodes = new Map(),
  connected = false,
  busy = false,
  refreshing = false,
  refreshTask = null,
  view = "map",
  selected = null,
  quickRevision = null,
  lastTap = null,
  focus = null,
  folded = new Set(),
  selectedDay = "",
  month = "",
  selectedNotes = "",
  noteIndex = 0,
  camera = null,
  pollTimer = null,
  pollDelay = 2000,
  mapExpanded = false,
  mapResizeObserver = null,
  mapViewport = null;
let formRevision = null,
  formAction = null;
const editor = $("editor"),
  fields = $("fields");
function message(text = "") {
  $("message").hidden = !text;
  $("message").textContent = text;
}
function status() {
  $("status").textContent = !connected
    ? "Disconnected"
    : busy
      ? "Saving…"
      : state?.saved
        ? "Connected · Saved"
        : "Connected · Unsaved changes";
  $("retry").hidden = !!state?.saved;
  $("retry").disabled = !connected || busy;
  $("submit").disabled = !connected || busy;
  $("add").disabled = !connected || busy;
  $("undo").disabled = !connected || busy || !state?.canUndo;
  $("redo").disabled = !connected || busy || !state?.canRedo;
  document.querySelectorAll("#quickAdd button").forEach((b) => {
    b.disabled =
      !connected ||
      busy ||
      (b.value === "sibling" && !nodes.get(selected)?.parent);
  });
  $("zone").textContent = state ? `Times: ${state.timezone}` : "";
}
async function api(path, body) {
  const response = await fetch("/api/" + path, {
    method: body ? "POST" : "GET",
    cache: "no-store",
    headers: {
      Authorization:
        "Bearer " + (sessionStorage.getItem("actiondraw-key") || ""),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(35000),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "Request failed");
    error.status = response.status;
    throw error;
  }
  return data;
}
async function refresh() {
  if (busy) return;
  if (refreshing) return refreshTask;
  refreshing = true;
  refreshTask = (async () => {
    try {
      const next = await api(state ? `state?since=${state.revision}` : "state"),
        wasDisconnected = !connected,
        changed =
          !state ||
          state.revision !== next.revision ||
          (!next.unchanged &&
            state.serverNow.slice(0, 10) !== next.serverNow.slice(0, 10));
      if (wasDisconnected) message("");
      if (next.unchanged) {
        Object.assign(state, next);
        pollDelay = Math.min(10000, pollDelay * 2);
      } else {
        state = next;
        nodes = new Map(state.nodes.map((n) => [n.id, n]));
        pollDelay = changed ? 2000 : Math.min(10000, pollDelay * 2);
      }
      connected = true;
      if (!nodes.has(focus)) focus = state.root;
      if (!nodes.has(selected)) selected = focus;
      if (!month) month = state.serverNow.slice(0, 7);
      if (changed) render();
    } catch (error) {
      connected = false;
      pollDelay = Math.min(10000, pollDelay * 2);
      message(
        error.status === 401
          ? error.message
          : "Connection lost. Keep this page open to preserve your draft. Reconnecting…",
      );
    } finally {
      refreshing = false;
      status();
      schedulePoll();
    }
  })();
  return refreshTask;
}

async function command(action, data = {}, revision = state?.revision) {
  if (!connected || busy)
    throw new Error("Wait until reconnected before submitting.");
  busy = true;
  clearTimeout(pollTimer);
  pollDelay = 2000;
  status();
  try {
    const result = await api("command", { action, revision, ...data });
    if (!result.saved)
      message(result.message || "Changes are not saved. Retry Save.");
    else message("");
    return result;
  } catch (error) {
    if (!error.status) {
      connected = false;
      message(
        "Connection interrupted. The edit may have reached the desktop. Reconnect and review before submitting again.",
      );
    }
    throw error;
  } finally {
    busy = false;
    if (refreshing) await refreshTask;
    await refresh();
    status();
  }
}
async function run(action, data = {}) {
  try {
    await command(action, data);
  } catch (e) {
    message(e.message);
  }
}
function openForm(title, build, submit) {
  $("editorTitle").textContent = title;
  fields.replaceChildren();
  $("editorError").replaceChildren();
  formRevision = state.revision;
  formAction = submit;
  $("submit").hidden = !submit;
  build();
  if (!editor.open) editor.showModal();
  status();
}
function field(label, value = "", type = "text") {
  const id = "field-" + fields.querySelectorAll("input,textarea,select").length;
  const l = el("label", label);
  l.htmlFor = id;
  const input = el(type === "textarea" ? "textarea" : "input");
  input.id = id;
  if (type !== "textarea") input.type = type;
  input.value = value ?? "";
  fields.append(l, input);
  return input;
}
function select(label, options, value) {
  const l = el("label", label),
    s = el("select");
  for (const [v, t] of options) {
    const o = el("option", t);
    o.value = v;
    s.append(o);
  }
  s.value = value ?? options[0]?.[0];
  l.append(s);
  fields.append(l);
  return s;
}
function check(label, value = false) {
  const l = el("label", label, "check"),
    c = el("input");
  c.type = "checkbox";
  c.checked = value;
  l.prepend(c);
  fields.append(l);
  return c;
}
function actions(items) {
  const row = el("div", undefined, "actions");
  for (const [text, fn, cls] of items) row.append(button(text, fn, cls));
  fields.append(row);
  return row;
}
$("editorForm").onsubmit = async (event) => {
  event.preventDefault();
  if (!formAction) return;
  try {
    await formAction(formRevision);
    editor.close();
  } catch (e) {
    $("editorError").textContent = e.message;
    if (e.status === 409) {
      const latest = el("details");
      latest.append(el("summary", "Review current project content"));
      latest.append(
        el(
          "pre",
          state.nodes
            .filter((n) => n.note || n.title)
            .map((n) => `${n.title}${n.note ? "\n" + n.note : ""}`)
            .join("\n\n"),
        ),
      );
      $("editorError").append(
        latest,
        button("Keep my draft and use refreshed version", () => {
          formRevision = state.revision;
          $("editorError").textContent =
            "Draft retained. Review it, then Save changes.";
        }),
      );
    }
  }
};
$("closeEditor").onclick = () => editor.close();
function focusNode(id) {
  focus = id;
  selected = id;
  folded.delete(id);
  camera = null;
  render();
}
function editNode(id) {
  const n = nodes.get(id);
  if (!n) return;
  let title, note;
  openForm(
    n.reference ? "Goal reference" : "Edit thought",
    () => {
      title = field("Title", n.title);
      note = field("Notes", n.note, "textarea");
      actions([
        [
          "Focus branch",
          () => {
            editor.close();
            focusNode(id);
          },
        ],
        ["Add child", () => addNode(id)],
        ["Add sibling", () => addNode(id, true)],
      ]);
      actions([
        [
          n.completed ? "Mark incomplete" : "Complete",
          () => nodeAction("complete", id),
        ],
        [n.bold ? "Normal text" : "Bold", () => nodeAction("bold", id)],
        [
          n.bookmarked ? "Remove bookmark" : "Bookmark",
          () => nodeAction("bookmark", id),
        ],
        [
          n.measureProgress ? "Hide progress" : "Measure progress",
          () => nodeAction("progress", id),
        ],
      ]);
      actions([
        ["Move / reorder", () => moveNode(id)],
        ["Left", () => nodeAction("side", id, { side: "left" })],
        ["Right", () => nodeAction("side", id, { side: "right" })],
      ]);
      actions([
        ["Reminder", () => reminderForm(n)],
        ["Deadline", () => deadlineForm(n)],
        ["Schedule weekday", () => scheduleForm(n)],
        ["Kanban", () => placementForm(n)],
      ]);
      actions([
        ["Add goal reference", () => referenceForm(id)],
        ...[
          !n.goalId
            ? ["Create goal", () => nodeAction("promote", id)]
            : ["Goal settings", () => goalForm(n.goalId)],
        ],
      ]);
      actions([
        ["Import / paste branch", () => importForm(id)],
        ["Copy / export branch", () => exportForm(id)],
      ]);
      if (n.id !== state.root)
        actions([
          [
            n.reference ? "Remove reference" : "Delete branch",
            () => {
              if (
                confirm(
                  n.reference
                    ? "Remove this reference placement?"
                    : "Delete this branch and its descendants?",
                )
              )
                nodeAction("delete", id);
            },
            "danger",
          ],
        ]);
    },
    (rev) =>
      command("edit", { node: id, title: title.value, note: note.value }, rev),
  );
}
async function nodeAction(action, node, data = {}) {
  try {
    await command(action, { node, ...data }, formRevision);
    editor.close();
  } catch (e) {
    $("editorError").textContent = e.message;
  }
}
function addNode(parent = focus, sibling = false) {
  let title;
  openForm(
    sibling ? "Add sibling" : "Add thought",
    () => {
      title = field("Title");
      title.required = true;
    },
    (rev) =>
      command(
        sibling ? "sibling" : "child",
        { node: parent, title: title.value },
        rev,
      ),
  );
}
function moveNode(id) {
  let target, placement;
  openForm(
    "Move branch",
    () => {
      target = select(
        "Destination",
        state.nodes.filter((n) => n.id !== id).map((n) => [n.id, n.title]),
      );
      placement = select("Position", [
        ["child", "Inside destination"],
        ["before", "Before destination"],
        ["after", "After destination"],
      ]);
    },
    (rev) =>
      command(
        "move",
        { node: id, target: target.value, placement: placement.value },
        rev,
      ),
  );
}
function referenceForm(id) {
  let goal;
  openForm(
    "Add goal reference",
    () => {
      goal = select(
        "Existing goal",
        state.goals.map((g) => [g.id, g.name]),
      );
    },
    (rev) => command("reference", { node: id, goal: goal.value }, rev),
  );
}
function reminderForm(n) {
  let at, notify;
  openForm(
    "Reminder",
    () => {
      at = field(
        `Date and time (${state.timezone}); empty clears`,
        n.reminderAt?.replace(" ", "T"),
        "datetime-local",
      );
      notify = check(
        "Send configured notification",
        n.reminderSendNotification,
      );
    },
    (rev) =>
      command(
        "reminder",
        { node: n.id, at: at.value, notify: notify.checked },
        rev,
      ),
  );
}
function deadlineForm(n) {
  let minutes;
  openForm(
    "Deadline",
    () => {
      minutes = field(
        "Minutes from now (0 clears)",
        n.deadlineDuration / 60 || 30,
        "number",
      );
      minutes.min = 0;
    },
    (rev) =>
      command("deadline", { node: n.id, minutes: Number(minutes.value) }, rev),
  );
}
function scheduleForm(n) {
  let day;
  openForm(
    "Schedule move to Ready",
    () => {
      fields.append(
        el(
          "p",
          `Moves to Ready at 08:00 ${state.timezone} on the next occurrence of the selected weekday, including today.`,
        ),
      );
      day = select(
        "Weekday",
        [
          ["-1", "Cancel schedule"],
          ...state.weekdays.map((d) => [String(d.weekday), d.label]),
        ],
        "0",
      );
    },
    (rev) =>
      command("schedule", { node: n.id, weekday: Number(day.value) }, rev),
  );
}
function placementForm(n, item) {
  const itemId =
    item?.itemId || (n.goalId ? "tab:" + n.goalId : "node:" + n.sourceId);
  let lane, hour;
  openForm(
    "Kanban placement",
    () => {
      lane = select(
        "Lane",
        [
          ["unscheduled", "Off board"],
          ["todo", "To Do"],
          ["ready", "Ready"],
          ["in_progress", "In Progress"],
          ["done", "Done"],
        ],
        item?.kanbanStatus || "ready",
      );
      hour = select(
        "Hourly slot (In Progress)",
        [
          ["-1", "No hour"],
          ...Array.from({ length: 10 }, (_, j) => {
            const i = j + 8;
            return [String(i), `${String(i).padStart(2, "0")}:00`];
          }),
        ],
        String(item?.kanbanSlotHour ?? -1),
      );
      actions([
        [
          "Set duration",
          () => durationForm(itemId, item?.kanbanDurationHours || 1),
        ],
      ]);
    },
    (rev) =>
      command(
        "kanban",
        { item: itemId, status: lane.value, hour: Number(hour.value) },
        rev,
      ),
  );
}
function durationForm(item, duration) {
  let input;
  openForm(
    "Kanban duration",
    () => {
      input = field("Hours", duration, "number");
      input.min = 1;
      input.max = 24;
    },
    (rev) => command("duration", { item, duration: Number(input.value) }, rev),
  );
}
function importForm(id) {
  let text;
  openForm(
    "Paste text or import OPML",
    () => {
      text = field("Indented text or OPML", "", "textarea");
      const file = field("Or choose a file", "", "file");
      file.accept = ".opml,.txt";
      file.onchange = async () => {
        if (file.files[0]) text.value = await file.files[0].text();
      };
    },
    (rev) => command("import", { node: id, text: text.value }, rev),
  );
}
async function exportForm(id) {
  let text;
  openForm(
    "Copy / export branch",
    () => {
      text = field("Select and copy this text", "", "textarea");
      text.readOnly = true;
      actions([
        [
          "Select text",
          () => {
            text.focus();
            text.select();
          },
        ],
        [
          "Download OPML",
          async () => {
            try {
              const r = await command("export", { node: id, format: "opml" });
              download(r.text, "branch.opml", "text/xml");
            } catch (e) {
              $("editorError").textContent = e.message;
            }
          },
        ],
      ]);
    },
    null,
  );
  try {
    text.value = (await command("export", { node: id, format: "text" })).text;
  } catch (e) {
    $("editorError").textContent = e.message;
  }
}
function download(text, name, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = el("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function goalForm(id) {
  const goal = state.goals.find((g) => g.id === id);
  if (!goal) return;
  let start, end;
  openForm(
    goal.name,
    () => {
      start = field("Start date (inclusive)", goal.start, "date");
      end = field("End date (inclusive)", goal.end, "date");
      actions([
        [
          "Rename",
          () => {
            let title;
            openForm(
              "Rename goal",
              () => {
                title = field("Name", goal.name);
              },
              (rev) =>
                command("goal_rename", { goal: id, title: title.value }, rev),
            );
          },
        ],
        [
          "Remove dates",
          async () => {
            try {
              await command(
                "goal_range",
                { goal: id, start: "", end: "" },
                formRevision,
              );
              editor.close();
            } catch (e) {
              $("editorError").textContent = e.message;
            }
          },
        ],
        [
          "Markdown notes",
          () => {
            selectedNotes = id;
            editor.close();
            setView("notes");
          },
        ],
      ]);
      actions([
        [
          "Delete goal",
          async () => {
            if (
              confirm(
                "Delete this goal workspace? Its mindmap thought is retained.",
              )
            ) {
              try {
                await command("goal_delete", { goal: id }, formRevision);
                editor.close();
              } catch (e) {
                $("editorError").textContent = e.message;
              }
            }
          },
          "danger",
        ],
      ]);
    },
    (rev) =>
      command(
        "goal_range",
        { goal: id, start: start.value, end: end.value },
        rev,
      ),
  );
}
function goalsForm() {
  openForm(
    "Goals",
    () => {
      actions([
        [
          "New goal",
          () => {
            let title;
            openForm(
              "New goal",
              () => {
                title = field("Name");
                title.required = true;
              },
              (rev) => command("goal_add", { title: title.value }, rev),
            );
          },
        ],
      ]);
      for (const g of state.goals) actions([[g.name, () => goalForm(g.id)]]);
    },
    null,
  );
}
function render() {
  if (!state) return;
  $("breadcrumbs").replaceChildren();
  $("bookmarks").replaceChildren();
  if (view === "outline" || view === "map") {
    const trail = [];
    let n = nodes.get(focus);
    while (n) {
      trail.unshift(n);
      n = nodes.get(n.parent);
    }
    for (const n of trail)
      $("breadcrumbs").append(button(n.title, () => focusNode(n.id)));
    for (const n of state.nodes.filter((n) => n.bookmarked))
      $("bookmarks").append(button("★ " + n.title, () => focusNode(n.id)));
  }
  $("mapDock").hidden = view !== "map";
  renderMapSearch();
  document.body.classList.toggle("mindmap-view", view === "map");
  document.body.classList.toggle("map-expanded", view === "map" && mapExpanded);
  mapResizeObserver?.disconnect();
  mapResizeObserver = null;
  $("content").replaceChildren();
  ({
    outline: renderOutline,
    map: renderMap,
    calendar: renderCalendar,
    kanban: renderKanban,
    notes: renderNotes,
  })[view]();
  updateMapControls();
  status();
}
function badges(n) {
  return [
    n.goalId ? "Goal" : "",
    n.reference ? "↗ Reference" : "",
    n.reminderActive ? "🔔 " + n.reminderAt : "",
    n.planVisible ? "▣ " + n.planTooltip.split("\n")[0] : "",
    n.measureProgress ? `${n.progressPercent}% complete` : "",
    n.priorityLevel ? "Priority " + n.priorityLevel : "",
    n.deadlineActive ? "Deadline active" : "",
  ]
    .filter(Boolean)
    .join(" · ");
}
function renderOutline() {
  const query = $("search").value.trim().toLowerCase(),
    rows = [];
  function visit(id, depth) {
    const n = nodes.get(id);
    if (!n) return;
    rows.push([n, depth]);
    if (!folded.has(id)) n.children.forEach((c) => visit(c, depth + 1));
  }
  if (query)
    state.nodes
      .filter((n) => (n.title + " " + n.note).toLowerCase().includes(query))
      .forEach((n) => rows.push([n, 0]));
  else visit(focus, 0);
  const fragment = document.createDocumentFragment();
  for (const [n, depth] of rows) {
    const row = el("div", undefined, "row");
    row.style.paddingLeft = Math.min(depth, 7) * 12 + "px";
    row.append(
      button(
        n.children.length ? (folded.has(n.id) ? "▸" : "▾") : "·",
        () => {
          folded.has(n.id) ? folded.delete(n.id) : folded.add(n.id);
          render();
        },
        "fold",
      ),
    );
    const b = button(
      (n.completed ? "✓ " : "") + n.title,
      () => editNode(n.id),
      "title" + (n.completed ? " completed" : ""),
    );
    if (n.bold) b.style.fontWeight = "bold";
    const info = badges(n);
    if (info) b.append(el("small", info));
    row.append(b);
    if (n.children.length) row.append(button("↗", () => focusNode(n.id)));
    fragment.append(row);
  }
  $("content").append(fragment);
  if (!rows.length)
    $("content").append(el("p", "No matching thoughts.", "muted"));
}
function renderMap() {
  const ns = "http://www.w3.org/2000/svg",
    svgEl = (tag, attrs) => {
      const n = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
      return n;
    };
  const toolbar = el("div", undefined, "actions"),
    wrap = el("div", undefined, "map-wrap"),
    svg = svgEl("svg", { "aria-label": "Mindmap" });
  wrap.append(svg);
  let visible = [];
  function visit(id) {
    const n = nodes.get(id);
    if (!n) return;
    visible.push(n);
    if (!folded.has(id)) n.children.forEach(visit);
  }
  visit(focus);
  if (!visible.length) return;
  const xmin = Math.min(...visible.map((n) => n.x)) - 25,
    ymin = Math.min(...visible.map((n) => n.y)) - 25,
    xmax = Math.max(...visible.map((n) => n.x + n.width)) + 25,
    ymax = Math.max(...visible.map((n) => n.y + n.height)) + 25;
  const fit = () => {
    const rect = wrap.getBoundingClientRect();
    const aspect = rect.width / Math.max(1, rect.height);
    const w = Math.max(xmax - xmin, (ymax - ymin) * aspect);
    const h = w / aspect;
    camera = { x: (xmin + xmax - w) / 2, y: (ymin + ymax - h) / 2, w, h };
    update();
  };
  function update() {
    if (camera)
      svg.setAttribute(
        "viewBox",
        `${camera.x} ${camera.y} ${camera.w} ${camera.h}`,
      );
  }
  toolbar.append(
    button("Up a branch", () =>
      focusNode(nodes.get(focus)?.parent || state.root),
    ),
    button("Whole map", () => focusNode(state.root)),
    button(mapExpanded ? "Exit expanded" : "Expand map", () => {
      mapExpanded = !mapExpanded;
      render();
    }),
    button("Fit", fit),
    button("＋", () => zoom(0.8)),
    button("−", () => zoom(1.25)),
    button("Expand all", () => {
      folded.clear();
      camera = null;
      render();
    }),
    button("Collapse branches", () => {
      for (const n of visible) if (n.id !== focus) folded.add(n.id);
      camera = null;
      render();
    }),
  );
  for (const b of toolbar.children) {
    if (
      ["Up a branch", "Whole map", "Expand all", "Collapse branches"].includes(
        b.textContent,
      )
    )
      b.classList.add("secondary-map-tool");
  }
  function zoom(f) {
    camera.x += (camera.w * (1 - f)) / 2;
    camera.y += (camera.h * (1 - f)) / 2;
    camera.w *= f;
    camera.h *= f;
    update();
  }
  const ids = new Set(visible.map((n) => n.id));
  for (const n of visible) {
    const p = nodes.get(n.parent);
    if (p && ids.has(p.id)) {
      const right = n.x > p.x;
      const x1 = p.x + (right ? p.width : 0),
        y1 = p.y + p.height / 2,
        x2 = n.x + (right ? 0 : n.width),
        y2 = n.y + n.height / 2;
      svg.append(
        svgEl("path", {
          d: `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`,
        }),
      );
    }
  }
  let moved = false,
    tapped = null,
    originPoint = null;
  for (const n of visible) {
    const group = svgEl("g", {
      tabindex: 0,
      role: "button",
      "aria-label": n.title,
      "data-node": n.id,
      "aria-pressed": String(n.id === selected),
      class: n.id === selected ? "selected-node" : "",
    });
    group.append(
      svgEl("rect", {
        x: n.x,
        y: n.y,
        width: n.width,
        height: n.height,
        rx: 8,
      }),
    );
    const text = svgEl("text", { x: n.x + 10, y: n.y + 22 });
    text.textContent =
      (n.completed ? "✓ " : "") +
      n.title.slice(0, 30) +
      (n.title.length > 30 ? "…" : "");
    group.append(text);
    group.onkeydown = (e) => {
      if (e.key === "Enter") selectMapNode(n.id);
      if (e.key === "F2") editNode(n.id);
    };
    svg.append(group);
  }
  const pointers = new Map();
  let previous = null;
  const gesture = () => {
    const a = [...pointers.values()];
    return {
      x: a.reduce((s, p) => s + p.x, 0) / a.length,
      y: a.reduce((s, p) => s + p.y, 0) / a.length,
      d: a.length > 1 ? Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y) : 0,
    };
  };
  svg.onpointerdown = (e) => {
    tapped = e.target.closest("g[data-node]")?.getAttribute("data-node");
    originPoint = { x: e.clientX, y: e.clientY };
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    previous = gesture();
    moved = pointers.size > 1;
    svg.setPointerCapture(e.pointerId);
  };
  svg.onpointermove = (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const next = gesture(),
      dx = next.x - previous.x,
      dy = next.y - previous.y;
    if (
      pointers.size > 1 ||
      Math.hypot(e.clientX - originPoint.x, e.clientY - originPoint.y) > 5
    )
      moved = true;
    const rect = svg.getBoundingClientRect();
    camera.x -= (dx * camera.w) / rect.width;
    camera.y -= (dy * camera.h) / rect.height;
    if (next.d && previous.d) zoom(previous.d / next.d);
    previous = next;
    update();
  };
  svg.onpointerup = (e) => {
    const open = !moved && pointers.size === 1 && tapped;
    pointers.delete(e.pointerId);
    previous = pointers.size ? gesture() : null;
    if (open) {
      if (lastTap?.id === tapped && performance.now() - lastTap.at < 350) {
        focusNode(tapped);
        lastTap = null;
      } else {
        selectMapNode(tapped);
        lastTap = { id: tapped, at: performance.now() };
      }
    }
  };
  svg.onpointercancel = (e) => {
    pointers.delete(e.pointerId);
    moved = true;
    previous = pointers.size ? gesture() : null;
  };
  svg.onwheel = (e) => {
    e.preventDefault();
    zoom(e.deltaY > 0 ? 1.15 : 0.87);
  };
  $("content").append(toolbar, wrap);
  function resizeMap() {
    const rect = wrap.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    if (camera && mapViewport) {
      const scale = Math.max(
        camera.w / mapViewport.width,
        camera.h / mapViewport.height,
      );
      const w = scale * rect.width,
        h = scale * rect.height;
      camera.x += (camera.w - w) / 2;
      camera.y += (camera.h - h) / 2;
      camera.w = w;
      camera.h = h;
      update();
    } else if (!camera) fit();
    else update();
    mapViewport = { width: rect.width, height: rect.height };
  }
  resizeMap();
  mapResizeObserver = new ResizeObserver(resizeMap);
  mapResizeObserver.observe(wrap);
}
function setView(next) {
  view = next;
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  render();
}
function dayString(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function renderCalendar() {
  const area = $("content"),
    controls = el("div", undefined, "actions");
  const [year, m] = month.split("-").map(Number);
  function shift(delta) {
    month = dayString(new Date(year, m - 1 + delta, 1)).slice(0, 7);
    render();
  }
  controls.append(
    button("←", () => shift(-1)),
    el("h3", month),
    button("→", () => shift(1)),
    button("Today", () => {
      month = state.serverNow.slice(0, 7);
      selectedDay = state.serverNow.slice(0, 10);
      render();
    }),
    button("All days", () => {
      selectedDay = "";
      render();
    }),
    button("New reminder", () => standaloneForm()),
  );
  area.append(controls);
  const grid = el("div", undefined, "calendar-grid");
  for (const d of ["M", "T", "W", "T", "F", "S", "S"])
    grid.append(el("small", d));
  const start = new Date(year, m - 1, 1);
  start.setDate(1 - ((start.getDay() + 6) % 7));
  for (let i = 0; i < 42; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const key = dayString(d);
    const count =
      state.goals.filter((g) => g.start && g.start <= key && g.end >= key)
        .length +
      state.reminders.filter((r) => r.reminderText.startsWith(key)).length;
    const b = button(
      String(d.getDate()),
      () => {
        selectedDay = key;
        render();
      },
      [
        selectedDay === key ? "chosen" : "",
        key.slice(0, 7) !== month ? "outside" : "",
        key === state.serverNow.slice(0, 10) ? "today" : "",
      ].join(" "),
    );
    if (count) b.append(el("small", `${count} planned`));
    grid.append(b);
  }
  area.append(
    grid,
    el("h3", selectedDay || "All scheduled goals and reminders"),
  );
  for (const g of state.goals.filter(
    (g) =>
      g.start &&
      (!selectedDay || (g.start <= selectedDay && g.end >= selectedDay)),
  )) {
    const card = el("div", undefined, "card");
    card.append(
      button(g.name, () => goalForm(g.id)),
      el("p", `${g.start} → ${g.end}`),
    );
    area.append(card);
  }
  for (const r of state.reminders.filter(
    (r) => !selectedDay || r.reminderText.startsWith(selectedDay),
  )) {
    const card = el("div", undefined, "card");
    card.append(
      button(r.title, () => editReminder(r)),
      el("p", `${r.reminderText} · ${r.tabName}`),
    );
    area.append(card);
  }
}
function standaloneForm(reminder) {
  let title, at, notify;
  openForm(
    "Project reminder",
    () => {
      title = field("Title", reminder?.title || "");
      at = field(
        `Date and time (${state.timezone})`,
        reminder?.reminderText.replace(" ", "T") ||
          (selectedDay || state.serverNow.slice(0, 10)) + "T09:00",
        "datetime-local",
      );
      notify = check(
        "Send configured notification",
        reminder?.sendNotification,
      );
      if (reminder)
        actions([
          [
            "Clear reminder",
            async () => {
              try {
                await command(
                  "standalone_reminder",
                  { index: reminder.standaloneIndex, at: "" },
                  formRevision,
                );
                editor.close();
              } catch (e) {
                $("editorError").textContent = e.message;
              }
            },
          ],
        ]);
    },
    (rev) =>
      command(
        "standalone_reminder",
        {
          index: reminder?.standaloneIndex ?? -1,
          title: title.value,
          at: at.value,
          notify: notify.checked,
        },
        rev,
      ),
  );
}
function editReminder(r) {
  if (r.kind === "standalone") return standaloneForm(r);
  if (r.nodeId) {
    const n = state.nodes.find((n) => n.sourceId === r.nodeId);
    if (n)
      return r.kind === "kanban_schedule" ? scheduleForm(n) : reminderForm(n);
  }
  const goal = state.goals[r.tabIndex];
  if (!goal) return;
  let at, notify;
  openForm(
    r.title,
    () => {
      at = field(
        `Date and time (${state.timezone}); empty clears`,
        r.reminderText.replace(" ", "T"),
        "datetime-local",
      );
      notify = check("Send notification", r.sendNotification);
    },
    (rev) =>
      command(
        "task_reminder",
        {
          goal: goal.id,
          index: r.taskIndex,
          at: at.value,
          notify: notify.checked,
        },
        rev,
      ),
  );
}
function renderKanban() {
  const board = el("div", undefined, "board");
  for (const [status, title] of [
    ["todo", "To Do"],
    ["ready", "Ready"],
    ["in_progress", "In Progress"],
    ["done", "Done"],
  ]) {
    const lane = el("section", undefined, "lane");
    lane.append(el("h2", title));
    for (const item of state.kanban.filter((i) => i.kanbanStatus === status)) {
      const card = el("div", undefined, "card");
      card.append(
        el("h3", item.name),
        button("Move / plan", () => placementForm(null, item)),
      );
      if (item.kanbanSlotHour >= 0)
        card.append(
          el(
            "p",
            `${String(item.kanbanSlotHour).padStart(2, "0")}:00 · ${item.kanbanDurationHours}h`,
          ),
        );
      const n = state.nodes.find(
        (n) =>
          item.itemId === "node:" + n.sourceId ||
          item.itemId === "tab:" + n.goalId,
      );
      if (n) card.append(button("Open", () => editNode(n.id)));
      lane.append(card);
    }
    board.append(lane);
  }
  $("content").append(
    board,
    el("p", "Use a thought’s Kanban action to add it to the board.", "muted"),
  );
}
function renderNotes() {
  const area = $("content"),
    chooser = el("select");
  for (const [id, title] of [
    ["", "Project notes"],
    ...state.goals.map((g) => [g.id, g.name]),
  ]) {
    const o = el("option", title);
    o.value = id;
    chooser.append(o);
  }
  if (!state.goals.some((g) => g.id === selectedNotes)) selectedNotes = "";
  chooser.value = selectedNotes;
  chooser.onchange = () => {
    selectedNotes = chooser.value;
    noteIndex = 0;
    render();
  };
  area.append(chooser);
  const tabs = selectedNotes
    ? state.goals.find((g) => g.id === selectedNotes).markdown
    : state.markdown;
  noteIndex = Math.min(noteIndex, tabs.length - 1);
  const bar = el("div", undefined, "note-tabs");
  tabs.forEach((t, i) =>
    bar.append(
      button(
        t.name,
        () => {
          noteIndex = i;
          render();
        },
        i === noteIndex ? "active" : "",
      ),
    ),
  );
  area.append(bar);
  area.append(el("pre", tabs[noteIndex]?.text || "No notes yet."));
  const row = el("div", undefined, "actions");
  row.append(
    button("Edit Markdown", () => markdownForm(tabs, noteIndex)),
    button("Add tab", () =>
      markdownForm([...tabs, { name: "New tab", text: "" }], tabs.length),
    ),
  );
  area.append(row);
}
function markdownForm(tabs, index) {
  let name, text;
  const draft = structuredClone(tabs);
  openForm(
    "Markdown notes",
    () => {
      name = field("Tab name", draft[index].name);
      text = field("Markdown", draft[index].text, "textarea");
      if (draft.length > 1)
        actions([
          [
            "Remove this tab",
            async () => {
              if (confirm("Remove this Markdown tab?")) {
                try {
                  await command(
                    "markdown",
                    {
                      goal: selectedNotes,
                      tabs: draft.filter((_, i) => i !== index),
                    },
                    formRevision,
                  );
                  editor.close();
                } catch (e) {
                  $("editorError").textContent = e.message;
                }
              }
            },
          ],
        ]);
    },
    (rev) => {
      draft[index] = { name: name.value, text: text.value };
      return command("markdown", { goal: selectedNotes, tabs: draft }, rev);
    },
  );
}
document
  .querySelectorAll("[data-view]")
  .forEach((b) => (b.onclick = () => setView(b.dataset.view)));
$("search").oninput = () => {
  if (view === "map") {
    renderMapSearch();
    return;
  }
  if (view !== "outline") setView("outline");
  else render();
};
$("add").onclick = () => {
  if (view === "map") $("quickTitle").focus();
  else addNode();
};
$("goals").onclick = () => state && goalsForm();
$("retry").onclick = () => run("save");
$("undo").onclick = () => run("undo");
$("redo").onclick = () => run("redo");
function schedulePoll() {
  clearTimeout(pollTimer);
  if (!document.hidden) pollTimer = setTimeout(refresh, pollDelay);
}
document.addEventListener("visibilitychange", () => {
  clearTimeout(pollTimer);
  if (!document.hidden) {
    pollDelay = 2000;
    refresh();
  }
});
window.addEventListener("online", () => {
  pollDelay = 2000;
  refresh();
});
$("mapTools").onclick = () => {
  const open = document.body.classList.toggle("map-tools-open");
  $("mapTools").setAttribute("aria-expanded", String(open));
  $("mapTools").textContent = open ? "Hide tools" : "Tools";
};
$("mapEdit").onclick = () => editNode(selected);
refresh();

// Selection and creation stay on the map; the full editor is only for details.
function selectMapNode(id, center = false) {
  const n = nodes.get(id);
  if (!n) return;
  selected = id;
  if (center) {
    let parent = nodes.get(n.parent);
    while (parent) {
      folded.delete(parent.id);
      parent = nodes.get(parent.parent);
    }
    let ancestor = n;
    while (ancestor && ancestor.id !== focus)
      ancestor = nodes.get(ancestor.parent);
    if (!ancestor) focus = n.parent || state.root;
    const rect = document.querySelector(".map-wrap")?.getBoundingClientRect();
    const width = Math.max(320, n.width * 1.5, (rect?.width || 390) * 0.75);
    const height = width * ((rect?.height || 400) / (rect?.width || 390));
    camera = {
      x: n.x + n.width / 2 - width / 2,
      y: n.y + n.height / 2 - height / 2,
      w: width,
      h: height,
    };
    render();
  } else {
    document.querySelectorAll("g[data-node]").forEach((g) => {
      const active = g.dataset.node === id;
      g.classList.toggle("selected-node", active);
      g.setAttribute("aria-pressed", String(active));
    });
    updateMapControls();
  }
}
function updateMapControls() {
  if (!state || view !== "map") return;
  const n = nodes.get(selected) || nodes.get(focus);
  if (!n) return;
  selected = n.id;
  $("mapSelection").textContent = n.title;
  $("quickContext").textContent =
    `Add beneath “${n.title}”, or beside it. Tap to select · double-tap to focus a branch.`;
  const parent = nodes.get(n.parent),
    siblings = parent?.children || [],
    index = siblings.indexOf(n.id);
  const row = $("mapActions");
  row.replaceChildren();
  function control(label, fn, enabled = true) {
    const b = button(label, fn);
    b.disabled = !enabled;
    row.append(b);
  }
  control("↑ Parent", () => selectMapNode(n.parent, true), !!parent);
  control(
    "↓ Child",
    () => selectMapNode(n.children[0], true),
    !!n.children.length,
  );
  control(
    "← Previous",
    () => selectMapNode(siblings[index - 1], true),
    index > 0,
  );
  control(
    "Next →",
    () => selectMapNode(siblings[index + 1], true),
    index >= 0 && index < siblings.length - 1,
  );
  control("Focus", () => focusNode(n.id));
  control(
    folded.has(n.id) ? "Expand" : "Collapse",
    () => {
      folded.has(n.id) ? folded.delete(n.id) : folded.add(n.id);
      render();
    },
    !!n.children.length,
  );

  $("quickSibling").disabled = !parent || !connected || busy;
}
$("quickTitle").addEventListener("input", () => {
  if (quickRevision === null) quickRevision = state?.revision;
});
// Retain the input focus on iOS: restoring it after a network await does not
// reliably reopen the software keyboard.
document.querySelectorAll("#quickAdd button").forEach((button) => {
  button.addEventListener("pointerdown", (event) => {
    if (document.activeElement === $("quickTitle")) event.preventDefault();
  });
});
$("quickAdd").onsubmit = async (event) => {
  event.preventDefault();
  const input = $("quickTitle"),
    title = input.value.trim(),
    target = selected;
  if (!title || !target || !connected || busy) return;
  const action = event.submitter?.value || "child";
  try {
    const result = await command(
      action,
      { node: target, title },
      quickRevision ?? state.revision,
    );
    input.value = "";
    quickRevision = null;
    if (result.nodeId) selectMapNode(result.nodeId, true);
    // Keep the keyboard open so another thought can be captured immediately.
    input.focus();
  } catch (error) {
    message(error.message);
    if (error.status === 409) {
      quickRevision = state.revision;
      message(
        error.message +
          " Your title is retained. Review the map, then press Child or Sibling again.",
      );
    }
  }
};

function renderMapSearch() {
  const box = $("mapSearchResults"),
    query = $("search").value.trim().toLowerCase();
  box.replaceChildren();
  box.hidden = view !== "map" || !query || !state;
  if (box.hidden) return;
  const matches = state.nodes.filter((n) =>
    (n.title + " " + n.note).toLowerCase().includes(query),
  );
  for (const n of matches.slice(0, 20))
    box.append(
      button(n.title, () => {
        $("search").value = "";
        selectMapNode(n.id, true);
        renderMapSearch();
      }),
    );
  if (!matches.length) box.append(el("small", "No matching nodes"));
}
