# Goals Skill Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship sidebar Goals with Cytoscape skill trees, unlock-all-parents, manual/task complete.

**Architecture:** SQLite tables + `app/goals.py` router; hook `complete_task_row`; static `goals.js` + vendor cytoscape; integrate `setView("goals")`.

**Tech Stack:** FastAPI, aiosqlite, Cytoscape.js (breadthfirst), vanilla JS.

## Global Constraints

- Do not alter `workout_goals` behavior.
- Soft-delete only; v1 single parent per child.
- Conventional commits; English commit messages.
- Cache-bump `app.js` / `index.html` / SW when shipping front.

---

### Task 1: Schema + unlock helpers + tests

**Files:** `app/db.py`, `app/goals.py`, `tests/test_goals_tree.py`

- [ ] Tables `goals`, `goal_nodes`, `goal_edges` in schema + `ensure_defaults`
- [ ] Pure `recompute_statuses(nodes, edges)` + failing tests then green
- [ ] Commit `feat(goals): schema and unlock recompute`

### Task 2: REST API + task-complete hook

**Files:** `app/goals.py`, `app/main.py`, `app/task_complete.py`

- [ ] CRUD endpoints; create goal → root node
- [ ] On task complete (non-recurring done path + after complete): mark linked nodes done + recompute
- [ ] Tests for locked 409, task link 409, tree shape
- [ ] Commit `feat(goals): API and task complete hook`

### Task 3: Frontend Cytoscape UI

**Files:** `static/vendor/cytoscape.min.js`, `static/goals.js`, `static/index.html`, `static/app.js`, `static/styles.css`, `static/sw.js`

- [ ] Vendor cytoscape; Goals nav + view; tabs + canvas + panel
- [ ] Game styles (medal/locked/open/done + glow)
- [ ] Wire `setView` / `refresh` / titles
- [ ] Commit `feat(goals): Cytoscape skill-tree UI`

### Task 4: Verify

- [ ] unittest goals; browser smoke on LAN/todo
- [ ] Update `context/context.md`
