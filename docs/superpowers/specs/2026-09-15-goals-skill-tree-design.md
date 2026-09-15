# Goals skill-tree design

Date: 2026-09-15  
Status: approved (user: «Реализуй»)

## Summary

Sidebar **Цели**: tabs = goals; each tab shows a **skill tree** (Cytoscape.js + breadthfirst layout). Nodes unlock when **all parents** are done. Complete via **manual check** or **linked NoteTask**. Game look: medal nodes, path edges, unlock glow. Separate from `workout_goals`.

## Data

- `goals(id, title, sort, deleted_at, created_at, updated_at)`
- `goal_nodes(id, goal_id, title, status, task_id NULL, sort, deleted_at, created_at, updated_at)`  
  status: `locked` | `open` | `done`
- `goal_edges(id, goal_id, parent_node_id, child_node_id)` — v1: one parent per child (tree)

Creating a goal also creates a **root** node (title = goal title, status `open`).

## Rules

- Unlock: all parents `done` → child `open`; else `locked` (roots always open unless done).
- Manual complete only if not `locked` → 409 if locked.
- Linking a task: open task, not already linked elsewhere → else 409. When that task completes → node `done` + recompute.
- Soft-delete goal cascades nodes/edges. Delete node soft-deletes subtree.

## API

- `GET/POST /api/goals`, `DELETE /api/goals/{id}`
- `GET /api/goals/{id}/tree` → `{ goal, nodes, edges }`
- `POST /api/goals/{id}/nodes` `{ parent_id, title, task_id? }`
- `PATCH /api/goals/{id}/nodes/{nid}` `{ title?, status?, task_id? }` (`status` done/open)
- `DELETE /api/goals/{id}/nodes/{nid}`

## UI

- `#view-goals`: tabs + Cytoscape canvas + detail panel (title, link task, complete, +child, delete).
- Theme accent distinct from finance (e.g. amber/gold for “medals”).

## Out of scope (v1)

Free drag edges, multi-parent DAG, XP/levels, replacing workout_goals.
