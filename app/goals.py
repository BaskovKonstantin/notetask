"""Goal skill-tree helpers and FastAPI router."""

from __future__ import annotations

from typing import Any, Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import require_auth
from .db import log_action, row_to_dict, utcnow
from .deps import get_db

router = APIRouter(prefix="/api/goals", tags=["goals"])


def recompute_statuses(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive locked/open from done parents. Done stays done."""
    by_id = {int(n["id"]): {**n} for n in nodes}
    parents: dict[int, list[int]] = {nid: [] for nid in by_id}
    for e in edges:
        child = int(e["child_node_id"])
        parent = int(e["parent_node_id"])
        if child in parents:
            parents[child].append(parent)

    for nid, node in by_id.items():
        if (node.get("status") or "").strip().lower() == "done":
            node["status"] = "done"
            continue
        pars = parents.get(nid) or []
        if not pars:
            node["status"] = "open"
            continue
        if all((by_id.get(p) or {}).get("status") == "done" for p in pars):
            node["status"] = "open"
        else:
            node["status"] = "locked"
    return list(by_id.values())


async def ensure_goals_tables(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS goals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          sort INTEGER NOT NULL DEFAULT 0,
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS goal_nodes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          goal_id INTEGER NOT NULL REFERENCES goals(id),
          title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          task_id INTEGER,
          sort INTEGER NOT NULL DEFAULT 0,
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS goal_edges (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          goal_id INTEGER NOT NULL REFERENCES goals(id),
          parent_node_id INTEGER NOT NULL,
          child_node_id INTEGER NOT NULL,
          UNIQUE(child_node_id)
        );
        """
    )
    await db.commit()


async def _fetch_goal(db: aiosqlite.Connection, goal_id: int) -> dict[str, Any] | None:
    cur = await db.execute(
        "SELECT * FROM goals WHERE id=? AND deleted_at IS NULL",
        (goal_id,),
    )
    row = await cur.fetchone()
    return row_to_dict(row) if row else None


async def _load_tree_parts(
    db: aiosqlite.Connection, goal_id: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cur = await db.execute(
        """
        SELECT * FROM goal_nodes
        WHERE goal_id=? AND deleted_at IS NULL
        ORDER BY sort, id
        """,
        (goal_id,),
    )
    nodes = [row_to_dict(r) for r in await cur.fetchall()]
    cur = await db.execute(
        "SELECT * FROM goal_edges WHERE goal_id=? ORDER BY id",
        (goal_id,),
    )
    edges = [row_to_dict(r) for r in await cur.fetchall()]
    return nodes, edges


async def persist_recomputed(db: aiosqlite.Connection, goal_id: int) -> list[dict[str, Any]]:
    nodes, edges = await _load_tree_parts(db, goal_id)
    updated = recompute_statuses(nodes, edges)
    now = utcnow()
    for n in updated:
        old = next((x for x in nodes if int(x["id"]) == int(n["id"])), None)
        if old and old.get("status") != n["status"]:
            await db.execute(
                "UPDATE goal_nodes SET status=?, updated_at=? WHERE id=?",
                (n["status"], now, n["id"]),
            )
    await db.commit()
    return updated


async def mark_goal_nodes_for_task(db: aiosqlite.Connection, task_id: int) -> None:
    cur = await db.execute(
        """
        SELECT id, goal_id, status FROM goal_nodes
        WHERE task_id=? AND deleted_at IS NULL
        """,
        (task_id,),
    )
    rows = [row_to_dict(r) for r in await cur.fetchall()]
    if not rows:
        return
    now = utcnow()
    goal_ids: set[int] = set()
    for row in rows:
        goal_ids.add(int(row["goal_id"]))
        if row.get("status") == "done":
            continue
        await db.execute(
            "UPDATE goal_nodes SET status='done', updated_at=? WHERE id=?",
            (now, row["id"]),
        )
    await db.commit()
    for gid in goal_ids:
        await persist_recomputed(db, gid)


async def _assert_task_linkable(
    db: aiosqlite.Connection, task_id: int, *, except_node_id: int | None = None
) -> dict[str, Any]:
    cur = await db.execute(
        "SELECT * FROM tasks WHERE id=? AND deleted_at IS NULL",
        (task_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    task = row_to_dict(row)
    cur = await db.execute(
        """
        SELECT id FROM goal_nodes
        WHERE task_id=? AND deleted_at IS NULL
          AND (? IS NULL OR id != ?)
        """,
        (task_id, except_node_id, except_node_id),
    )
    other = await cur.fetchone()
    if other:
        raise HTTPException(409, "Task already linked to another goal node")
    return task


async def _soft_delete_subtree(db: aiosqlite.Connection, goal_id: int, root_id: int) -> None:
    nodes, edges = await _load_tree_parts(db, goal_id)
    children: dict[int, list[int]] = {}
    for e in edges:
        children.setdefault(int(e["parent_node_id"]), []).append(int(e["child_node_id"]))
    stack = [root_id]
    to_delete: list[int] = []
    while stack:
        nid = stack.pop()
        to_delete.append(nid)
        stack.extend(children.get(nid) or [])
    now = utcnow()
    for nid in to_delete:
        await db.execute(
            "UPDATE goal_nodes SET deleted_at=?, updated_at=? WHERE id=? AND goal_id=?",
            (now, now, nid, goal_id),
        )
        await db.execute(
            "DELETE FROM goal_edges WHERE child_node_id=? OR parent_node_id=?",
            (nid, nid),
        )
    await db.commit()


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class NodeCreate(BaseModel):
    parent_id: int
    title: str = Field(min_length=1, max_length=200)
    task_id: int | None = None


class NodePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["done", "open"] | None = None
    task_id: int | None = None
    clear_task: bool = False


@router.get("")
async def list_goals(
    db: aiosqlite.Connection = Depends(get_db),
    _user: None = Depends(require_auth),
):
    cur = await db.execute(
        "SELECT * FROM goals WHERE deleted_at IS NULL ORDER BY sort, id"
    )
    return [row_to_dict(r) for r in await cur.fetchall()]


@router.post("")
async def create_goal(
    body: GoalCreate,
    db: aiosqlite.Connection = Depends(get_db),
    _user: None = Depends(require_auth),
):
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "title required")
    now = utcnow()
    cur = await db.execute(
        "SELECT COALESCE(MAX(sort), 0) + 1 AS s FROM goals WHERE deleted_at IS NULL"
    )
    sort = int((await cur.fetchone())["s"])
    cur = await db.execute(
        "INSERT INTO goals(title, sort, created_at, updated_at) VALUES (?,?,?,?)",
        (title, sort, now, now),
    )
    goal_id = int(cur.lastrowid)
    cur = await db.execute(
        """
        INSERT INTO goal_nodes(goal_id, title, status, sort, created_at, updated_at)
        VALUES (?,?,?,?,?,?)
        """,
        (goal_id, title, "open", 0, now, now),
    )
    await log_action(db, "created", "goal", goal_id, {"title": title})
    await db.commit()
    goal = await _fetch_goal(db, goal_id)
    return goal


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _user: None = Depends(require_auth),
):
    goal = await _fetch_goal(db, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    now = utcnow()
    await db.execute(
        "UPDATE goals SET deleted_at=?, updated_at=? WHERE id=?",
        (now, now, goal_id),
    )
    await db.execute(
        "UPDATE goal_nodes SET deleted_at=?, updated_at=? WHERE goal_id=? AND deleted_at IS NULL",
        (now, now, goal_id),
    )
    await db.execute("DELETE FROM goal_edges WHERE goal_id=?", (goal_id,))
    await log_action(db, "deleted", "goal", goal_id, {"title": goal["title"]})
    await db.commit()
    return {"ok": True}


@router.get("/{goal_id}/tree")
async def get_tree(
    goal_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _user: None = Depends(require_auth),
):
    goal = await _fetch_goal(db, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    nodes = await persist_recomputed(db, goal_id)
    _, edges = await _load_tree_parts(db, goal_id)
    return {"goal": goal, "nodes": nodes, "edges": edges}


@router.post("/{goal_id}/nodes")
async def create_node(
    goal_id: int,
    body: NodeCreate,
    db: aiosqlite.Connection = Depends(get_db),
    _user: None = Depends(require_auth),
):
    goal = await _fetch_goal(db, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "title required")
    cur = await db.execute(
        "SELECT * FROM goal_nodes WHERE id=? AND goal_id=? AND deleted_at IS NULL",
        (body.parent_id, goal_id),
    )
    parent = await cur.fetchone()
    if not parent:
        raise HTTPException(404, "Parent node not found")
    task_id = body.task_id
    if task_id is not None:
        await _assert_task_linkable(db, task_id)
    now = utcnow()
    cur = await db.execute(
        "SELECT COALESCE(MAX(sort), 0) + 1 AS s FROM goal_nodes WHERE goal_id=? AND deleted_at IS NULL",
        (goal_id,),
    )
    sort = int((await cur.fetchone())["s"])
    # provisional locked; recompute will open if parent done
    cur = await db.execute(
        """
        INSERT INTO goal_nodes(goal_id, title, status, task_id, sort, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (goal_id, title, "locked", task_id, sort, now, now),
    )
    node_id = int(cur.lastrowid)
    await db.execute(
        """
        INSERT INTO goal_edges(goal_id, parent_node_id, child_node_id)
        VALUES (?,?,?)
        """,
        (goal_id, body.parent_id, node_id),
    )
    await log_action(
        db, "created", "goal_node", node_id, {"goal_id": goal_id, "title": title}
    )
    await db.commit()
    await persist_recomputed(db, goal_id)
    cur = await db.execute("SELECT * FROM goal_nodes WHERE id=?", (node_id,))
    return row_to_dict(await cur.fetchone())


@router.patch("/{goal_id}/nodes/{node_id}")
async def patch_node(
    goal_id: int,
    node_id: int,
    body: NodePatch,
    db: aiosqlite.Connection = Depends(get_db),
    _user: None = Depends(require_auth),
):
    goal = await _fetch_goal(db, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    cur = await db.execute(
        "SELECT * FROM goal_nodes WHERE id=? AND goal_id=? AND deleted_at IS NULL",
        (node_id, goal_id),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Node not found")
    node = row_to_dict(row)
    title = node["title"]
    status = node["status"]
    task_id = node.get("task_id")

    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(400, "title required")

    if body.clear_task:
        task_id = None
    elif body.task_id is not None:
        await _assert_task_linkable(db, body.task_id, except_node_id=node_id)
        task_id = body.task_id

    if body.status == "done":
        if status == "locked":
            raise HTTPException(409, "Cannot complete locked node")
        status = "done"
    elif body.status == "open":
        status = "open"

    now = utcnow()
    await db.execute(
        """
        UPDATE goal_nodes SET title=?, status=?, task_id=?, updated_at=?
        WHERE id=?
        """,
        (title, status, task_id, now, node_id),
    )
    await log_action(
        db,
        "updated",
        "goal_node",
        node_id,
        {"goal_id": goal_id, "title": title, "status": status},
    )
    await db.commit()
    await persist_recomputed(db, goal_id)
    cur = await db.execute("SELECT * FROM goal_nodes WHERE id=?", (node_id,))
    return row_to_dict(await cur.fetchone())


@router.delete("/{goal_id}/nodes/{node_id}")
async def delete_node(
    goal_id: int,
    node_id: int,
    db: aiosqlite.Connection = Depends(get_db),
    _user: None = Depends(require_auth),
):
    goal = await _fetch_goal(db, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    cur = await db.execute(
        "SELECT * FROM goal_nodes WHERE id=? AND goal_id=? AND deleted_at IS NULL",
        (node_id, goal_id),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Node not found")
    # forbid deleting sole root if it has no parent and is the only path — allow but goal empty
    cur = await db.execute(
        "SELECT COUNT(*) AS c FROM goal_edges WHERE child_node_id=?",
        (node_id,),
    )
    is_root = int((await cur.fetchone())["c"]) == 0
    if is_root:
        cur = await db.execute(
            "SELECT COUNT(*) AS c FROM goal_nodes WHERE goal_id=? AND deleted_at IS NULL",
            (goal_id,),
        )
        if int((await cur.fetchone())["c"]) == 1:
            raise HTTPException(409, "Cannot delete the only root node; delete the goal")
    await _soft_delete_subtree(db, goal_id, node_id)
    await persist_recomputed(db, goal_id)
    await log_action(db, "deleted", "goal_node", node_id, {"goal_id": goal_id})
    return {"ok": True}


def register_goals(app) -> None:
    app.include_router(router)
