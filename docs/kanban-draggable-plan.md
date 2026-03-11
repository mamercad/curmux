# Plan: Kanban draggable (web UI)

**Backlog item:** kanban draggable  
**Source:** Task board (curmux project), status todo

## Goal

Allow users to move task cards between columns (todo → claimed → done) in the web dashboard by drag-and-drop. No new dependencies; use HTML5 DnD and existing REST API.

## Current state

- **Board:** Three columns (todo, claimed, done). Tasks rendered as `.task-card` divs; no drag handlers.
- **API:** GET/POST `/api/tasks`, POST `.../claim`, POST `.../done`, DELETE `.../tasks/{id}`. No generic update endpoint; status changes are done via claim/done only. There is no way to “unclaim” (move back to todo) or to set status from the UI without claim/done semantics.

## Approach

1. **Backend:** Add `PATCH /api/tasks/{id}` for partial updates so the UI can move a card to any column with a single call.
2. **Frontend:** Make cards draggable and columns drop targets; on drop call PATCH then refresh (or optimistically update).

---

## 1. Backend: PATCH /api/tasks/{id}

- **Method:** PATCH  
- **Path:** `/api/tasks/{id}`  
- **Body (optional):** `{ "status": "todo" | "claimed" | "done", "claimed_by": "" }`

**Semantics:**

- **status**
  - `todo`: set `status='todo'`, clear `claimed_by` and `claimed_at`.
  - `claimed`: set `status='claimed'`, set `claimed_at=now`; if `claimed_by` provided set it, else leave `claimed_by` unchanged (or leave null for “unassigned” claimed).
  - `done`: set `status='done'`, set `completed_at=now`; leave `claimed_by`/`claimed_at` as-is for history.
- Validate `status` is one of the three; 400 on bad input. 404 if task id not found.
- Return `{ "ok": true, "id": "..." }` on success.

**Implementation notes:**

- In `curmux`: add `do_PATCH` (or handle PATCH in the existing request router), route `PATCH /api/tasks/{id}` (no trailing `/claim` or `/done`) to a new handler e.g. `_patch_task(task_id, body)`.
- Use a single `UPDATE tasks SET ... WHERE id=?` with conditional fields; commit and return.

**Docs:** Update the in-file API reference (and AGENTS.md if it lists endpoints) to document `PATCH /api/tasks/{id}`.

---

## 2. Frontend: Drag-and-drop

- **Cards:** Each `.task-card` gets `draggable="true"` and `data-task-id="{id}"`. Store task id (and optionally current status) in `data-*` for the drop handler.
- **Columns:** Each `.board-col` is a drop target with `data-status="todo"` | `"claimed"` | `"done"` (already implied by column order; set explicitly in the template).
- **Events:**
  - `dragstart` on card: set `dataTransfer.effectAllowed = 'move'`, `dataTransfer.setData('text/plain', taskId)` (and optionally `application/json` with `{ id, status }`).
  - `dragend` on card: optional (e.g. remove a “dragging” class).
  - `dragover` on column: `preventDefault()`, set `dataTransfer.dropEffect = 'move'`, optionally add class for highlight (e.g. `.board-col.drag-over`).
  - `dragleave` on column: remove highlight class.
  - `drop` on column: `preventDefault()`, read task id from `dataTransfer.getData('text/plain')`, read target status from column `data-status`. If same as current status, no-op. Else `PATCH API+'/api/tasks/'+id` with body `{ status: targetStatus }`. On success: call `renderBoard()` (or optimistically move the card node and then refresh once). On failure: show a small message or revert.
- **Accessibility:** Ensure keyboard users can still use the board (e.g. “Add task” and refresh). Optional follow-up: keyboard move (e.g. select card, arrow keys to change column). Not required for this plan.

**Implementation notes:**

- All in the existing inline JS in `DASHBOARD_HTML`; no new script tags or libraries.
- In `renderBoard()`, when building the column HTML, add `data-status="${status}"` on the column div. When building each card, add `draggable="true"` and `data-task-id="${esc(t.id)}"` and the event handlers (e.g. `ondragstart="..."` and pass task id; use a small helper like `window.boardDragStart(event, id)` and `window.boardDrop(event, status)` so the template stays readable).
- Optional: add a `.dragging` class on the card being dragged and a `.drag-over` class on the column under the cursor; add minimal CSS (e.g. opacity on dragging card, border/background on drag-over column).

---

## 3. Pure API tests

Test the task API (including the new PATCH endpoint) with **curl** or a small script. No browser; server must be running (`curmux serve --no-tls --port 8833`). Base URL: `http://localhost:8833`.

### Cases to cover

| # | Action | Expected |
|---|--------|----------|
| 1 | `POST /api/tasks` with `{"project":"apitest","title":"PATCH target","description":""}` | 200, `{"ok":true,"id":"apitest-XXXXXX"}`; store `id`. |
| 2 | `GET /api/tasks?status=todo` | 200; response includes task from (1) with `status: "todo"`. |
| 3 | `PATCH /api/tasks/{id}` with `{"status":"claimed","claimed_by":"test-agent"}` | 200, `{"ok":true,"id":"..."}`. |
| 4 | `GET /api/tasks` (or `?status=claimed`) | 200; task has `status: "claimed"`, `claimed_by: "test-agent"`, `claimed_at` set. |
| 5 | `PATCH /api/tasks/{id}` with `{"status":"done"}` | 200. |
| 6 | `GET /api/tasks` | 200; task has `status: "done"`, `completed_at` set. |
| 7 | `PATCH /api/tasks/{id}` with `{"status":"todo"}` | 200. |
| 8 | `GET /api/tasks` | 200; task has `status: "todo"`, `claimed_by`/`claimed_at` cleared. |
| 9 | `PATCH /api/tasks/{id}` with `{"status":"invalid"}` | 400. |
| 10 | `PATCH /api/tasks/nonexistent-id` with `{"status":"done"}` | 404. |

### Cleanup

- `DELETE /api/tasks/{id}` for the task created in (1), or use a dedicated project and filter in GET so test data is isolated.

### How to run

- **Option A:** Inline in the plan or README as a copy-paste curl sequence (create task → PATCH lifecycle → GET assertions → invalid/404 cases → delete).
- **Option B:** Shell script (e.g. `tests/api-tasks.sh`) that parses the created task id from POST response, runs the PATCH/GET checks, and exits non-zero on failure.
- **Option C:** Justfile target (e.g. `just test-api`) that runs the script; requires server up or starts it in the background.

No new dependencies; `curl` and `jq` (optional, for parsing JSON) are sufficient.

---

## 4. Functional testing with agent-browser

Use the **agent-browser** skill to run repeatable functional tests against the dashboard. Prerequisite: `curmux serve` (and optionally the dashboard) running; agent-browser available (`npx agent-browser` or `agent-browser` in PATH).

**Base URL:** `http://localhost:8833` (or the port used by `curmux serve`). Use `--no-tls` so the URL is HTTP.

### Test flow

1. **Navigate and open Board**
   - `agent-browser open http://localhost:8833`
   - `agent-browser wait --load networkidle`
   - `agent-browser snapshot -i`
   - Click the “Board” tab (e.g. `agent-browser click @eN` where ref points to the Board tab).
   - `agent-browser snapshot -i` (refresh refs after tab switch).

2. **Ensure at least one todo task**
   - If the todo column is empty: use “New task title” + “Project” + “Add” to create a task, then snapshot again to get refs for the new card.

3. **Verify PATCH from API (optional but recommended)**
   - Before or after UI testing: `curl -X PATCH http://localhost:8833/api/tasks/<id> -H "Content-Type: application/json" -d '{"status":"done"}'` and confirm 200 and board state via GET /api/tasks or via the next snapshot.

4. **Test drag-and-drop in the UI**
   - **Option A (agent-browser drag):** If agent-browser supports drag (e.g. `agent-browser drag @eCard @eColumn` or similar), drag a task card from the todo column and drop it on the done column, then snapshot and assert the card appears under “done” and its text/task id is correct.
   - **Option B (indirect verification):** If native DnD is not scriptable, use the “Add task” flow and PATCH via API to move the task; then refresh the page (or re-open Board) and snapshot to verify the card appears in the target column. This validates that the board reflects API state; manual check for actual drag remains.

5. **Assertions**
   - After a move (via DnD or PATCH + refresh): take a snapshot; confirm the task id or title appears in the expected column (e.g. under “done (1)”).
   - Optional: `agent-browser get text body` and grep for the task id and the word “done” in the same context.

### Command sketch (concise)

```bash
# Server must be running: curmux serve --no-tls --port 8833
agent-browser open http://localhost:8833 && agent-browser wait --load networkidle && agent-browser snapshot -i
# Click Board tab (use ref from snapshot), then snapshot -i again
# Add task if needed: fill title, fill project, click Add; snapshot -i
# Drag card to done column (if supported), or PATCH task via curl then:
agent-browser open http://localhost:8833 && agent-browser wait --load networkidle && agent-browser snapshot -i
# Verify task appears in done column (inspect snapshot or get text body)
```

### Where to document the test

- Either: a short “Testing” subsection in this plan (this section) and/or a one-line note in the repo README (“Run dashboard tests with agent-browser against http://localhost:8833”).
- Or: a small script or justfile target that runs the above steps (open → Board → add task → PATCH → refresh → snapshot) for CI or local runs.

---

## 5. Order of work

| Step | What | Parallel? |
|------|------|-----------|
| 1 | Implement PATCH /api/tasks/{id} and _patch_task in curmux | No |
| 2 | Update API docs (in-file + AGENTS.md) for PATCH | No |
| 3 | Add data-task-id, data-status, draggable and DnD handlers in renderBoard() | No |
| 4 | Optional: .dragging / .drag-over CSS | No |
| 5 | Run pure API tests (curl or script per §3) | No |
| 6 | Run functional test with agent-browser (open dashboard → Board → add task → move via DnD or PATCH → verify) | No |

Can be done in one session; no need to split across agents.

---

## 6. Acceptance

- Dragging a card from one column and dropping it on another updates the task status via PATCH and the board re-renders with the card in the new column.
- Moving to “todo” clears claim; moving to “claimed” sets claimed_at (and optionally claimed_by); moving to “done” sets completed_at.
- No console errors; works in supported browsers (Chrome, Firefox, Safari).
- **Pure API tests (§3):** All cases (create → PATCH todo/claimed/done/todo → invalid status → 404) pass when run against a running server.
- **Agent-browser test (§4):** Following the flow (open dashboard, Board tab, add task if needed, move card via DnD or PATCH + refresh) ends with the task visible in the target column in a snapshot or `get text body`.

---

## 7. Out of scope (later)

- Editable cards in place (separate backlog item).
- Kanban cards timestamps / description (separate backlog items).
- Touch drag-and-drop tuning (optional polish).
