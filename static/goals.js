/* Goals skill-tree view — Cytoscape.js */
(function () {
  const GOLD = "#c9a227";
  const GOLD_DIM = "#6b5a28";
  const PATH = "#8a7340";
  const LOCKED_BG = "#3a3a3a";
  const OPEN_BG = "#c9a227";
  const DONE_BG = "#2a7a4b";

  let cy = null;
  let activeGoalId = null;
  let selectedNodeId = null;
  let treeCache = null;

  function $(id) {
    return document.getElementById(id);
  }

  function api() {
    return window.notetaskApi;
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function medalStyle() {
    return [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-valign": "bottom",
          "text-margin-y": 8,
          color: "#e8e0d0",
          "font-size": 12,
          "font-family": "Manrope, sans-serif",
          width: 48,
          height: 48,
          "background-color": LOCKED_BG,
          "border-width": 3,
          "border-color": GOLD_DIM,
          "text-wrap": "wrap",
          "text-max-width": 100,
        },
      },
      {
        selector: "node[status = 'open']",
        style: {
          "background-color": OPEN_BG,
          "border-color": "#f0d878",
          "shadow-blur": 12,
          "shadow-color": GOLD,
          "shadow-opacity": 0.55,
          "shadow-offset-x": 0,
          "shadow-offset-y": 0,
        },
      },
      {
        selector: "node[status = 'done']",
        style: {
          "background-color": DONE_BG,
          "border-color": "#5ecf8a",
          "shadow-blur": 16,
          "shadow-color": "#5ecf8a",
          "shadow-opacity": 0.6,
          "shadow-offset-x": 0,
          "shadow-offset-y": 0,
        },
      },
      {
        selector: "node[status = 'locked']",
        style: {
          "background-color": LOCKED_BG,
          "border-color": "#555",
          opacity: 0.55,
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-width": 5,
          "border-color": "#fff3c4",
        },
      },
      {
        selector: "edge",
        style: {
          width: 3,
          "line-color": PATH,
          "curve-style": "bezier",
          "target-arrow-shape": "triangle",
          "target-arrow-color": PATH,
          "arrow-scale": 0.9,
        },
      },
    ];
  }

  function toElements(tree) {
    const nodes = (tree.nodes || []).map((n) => ({
      data: {
        id: String(n.id),
        label: n.title,
        status: n.status,
        task_id: n.task_id,
        raw: n,
      },
    }));
    const edges = (tree.edges || []).map((e) => ({
      data: {
        id: `e${e.id}`,
        source: String(e.parent_node_id),
        target: String(e.child_node_id),
      },
    }));
    return nodes.concat(edges);
  }

  function ensureCy() {
    const el = $("goals-cy");
    if (!el || typeof cytoscape === "undefined") return null;
    if (cy) return cy;
    cy = cytoscape({
      container: el,
      style: medalStyle(),
      layout: { name: "breadthfirst", directed: true, padding: 40, spacingFactor: 1.35 },
      minZoom: 0.4,
      maxZoom: 2.5,
      wheelSensitivity: 0.35,
    });
    cy.on("tap", "node", (evt) => {
      selectedNodeId = Number(evt.target.id());
      renderPanel();
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        selectedNodeId = null;
        renderPanel();
      }
    });
    return cy;
  }

  function renderTabs(goals) {
    const tabs = $("goals-tabs");
    if (!tabs) return;
    const bits = (goals || [])
      .map(
        (g) =>
          `<button type="button" class="goals-tab${g.id === activeGoalId ? " active" : ""}" data-goal-id="${g.id}">${escapeHtml(g.title)}</button>`
      )
      .join("");
    tabs.innerHTML =
      bits +
      `<button type="button" class="goals-tab goals-tab-add" id="goals-add" title="Новая цель">+</button>`;
  }

  function renderPanel() {
    const panel = $("goals-panel");
    if (!panel) return;
    if (!selectedNodeId || !treeCache) {
      panel.innerHTML = `<p class="goals-panel-empty">Выбери узел на дереве</p>`;
      return;
    }
    const node = (treeCache.nodes || []).find((n) => Number(n.id) === selectedNodeId);
    if (!node) {
      panel.innerHTML = `<p class="goals-panel-empty">Узел не найден</p>`;
      return;
    }
    const statusLabel =
      node.status === "done" ? "Пройден" : node.status === "open" ? "Открыт" : "Закрыт";
    panel.innerHTML = `
      <div class="goals-panel-head">
        <strong>${escapeHtml(node.title)}</strong>
        <span class="goals-status goals-status-${escapeHtml(node.status)}">${statusLabel}</span>
      </div>
      <p class="goals-panel-meta">${node.task_id ? `Задача #${node.task_id}` : "Без задачи"}</p>
      <div class="goals-panel-actions">
        ${
          node.status === "open"
            ? `<button type="button" class="btn" data-goal-done>Выполнить</button>`
            : ""
        }
        ${
          node.status === "done"
            ? `<button type="button" class="btn ghost" data-goal-reopen>Открыть снова</button>`
            : ""
        }
        <button type="button" class="btn ghost" data-goal-add-child>+ ребёнок</button>
        <button type="button" class="btn ghost" data-goal-link-task>Привязать задачу</button>
        ${
          node.task_id
            ? `<button type="button" class="btn ghost" data-goal-unlink>Отвязать</button>`
            : ""
        }
        <button type="button" class="btn warn ghost" data-goal-del-node>Удалить узел</button>
      </div>
    `;
  }

  async function loadGoalsList() {
    const goals = await api()("/api/goals");
    if (!activeGoalId && goals.length) activeGoalId = goals[0].id;
    if (activeGoalId && !goals.some((g) => g.id === activeGoalId)) {
      activeGoalId = goals[0]?.id ?? null;
    }
    renderTabs(goals);
    return goals;
  }

  async function loadTree() {
    const graph = ensureCy();
    if (!activeGoalId) {
      treeCache = null;
      if (graph) {
        graph.elements().remove();
      }
      $("goals-empty")?.classList.remove("hidden");
      renderPanel();
      return;
    }
    $("goals-empty")?.classList.add("hidden");
    treeCache = await api()(`/api/goals/${activeGoalId}/tree`);
    if (!graph) return;
    const prev = selectedNodeId;
    graph.elements().remove();
    graph.add(toElements(treeCache));
    graph.layout({ name: "breadthfirst", directed: true, padding: 40, spacingFactor: 1.35 }).run();
    graph.fit(undefined, 40);
    if (prev && graph.$id(String(prev)).nonempty()) {
      selectedNodeId = prev;
      graph.$id(String(prev)).select();
    } else {
      selectedNodeId = null;
    }
    renderPanel();
  }

  async function loadGoalsView() {
    await loadGoalsList();
    await loadTree();
  }

  async function onAddGoal() {
    const title = prompt("Название цели");
    if (!title || !title.trim()) return;
    const g = await api()("/api/goals", { method: "POST", body: JSON.stringify({ title: title.trim() }) });
    activeGoalId = g.id;
    selectedNodeId = null;
    await loadGoalsView();
  }

  async function onDeleteGoal() {
    if (!activeGoalId) return;
    if (!confirm("Удалить цель и всё дерево?")) return;
    await api()(`/api/goals/${activeGoalId}`, { method: "DELETE" });
    activeGoalId = null;
    selectedNodeId = null;
    await loadGoalsView();
  }

  document.addEventListener("click", async (e) => {
    const tab = e.target.closest?.("[data-goal-id]");
    if (tab && tab.closest("#goals-tabs")) {
      activeGoalId = Number(tab.dataset.goalId);
      selectedNodeId = null;
      await loadGoalsView();
      return;
    }
    if (e.target.closest?.("#goals-add")) {
      await onAddGoal();
      return;
    }
    if (e.target.closest?.("#goals-delete")) {
      await onDeleteGoal();
      return;
    }
    if (!e.target.closest?.("#goals-panel")) return;
    if (!selectedNodeId || !activeGoalId) return;

    if (e.target.closest("[data-goal-done]")) {
      await api()(`/api/goals/${activeGoalId}/nodes/${selectedNodeId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "done" }),
      });
      await loadTree();
      return;
    }
    if (e.target.closest("[data-goal-reopen]")) {
      await api()(`/api/goals/${activeGoalId}/nodes/${selectedNodeId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "open" }),
      });
      await loadTree();
      return;
    }
    if (e.target.closest("[data-goal-add-child]")) {
      const title = prompt("Шаг (дочерний узел)");
      if (!title || !title.trim()) return;
      await api()(`/api/goals/${activeGoalId}/nodes`, {
        method: "POST",
        body: JSON.stringify({ parent_id: selectedNodeId, title: title.trim() }),
      });
      await loadTree();
      return;
    }
    if (e.target.closest("[data-goal-link-task]")) {
      const raw = prompt("ID задачи задачи NoteTask");
      if (!raw) return;
      const taskId = Number(raw);
      if (!Number.isFinite(taskId)) {
        alert("Нужен числовой id");
        return;
      }
      try {
        await api()(`/api/goals/${activeGoalId}/nodes/${selectedNodeId}`, {
          method: "PATCH",
          body: JSON.stringify({ task_id: taskId }),
        });
        await loadTree();
      } catch (err) {
        alert(String(err.message || err));
      }
      return;
    }
    if (e.target.closest("[data-goal-unlink]")) {
      await api()(`/api/goals/${activeGoalId}/nodes/${selectedNodeId}`, {
        method: "PATCH",
        body: JSON.stringify({ clear_task: true }),
      });
      await loadTree();
      return;
    }
    if (e.target.closest("[data-goal-del-node]")) {
      if (!confirm("Удалить узел и потомков?")) return;
      try {
        await api()(`/api/goals/${activeGoalId}/nodes/${selectedNodeId}`, { method: "DELETE" });
        selectedNodeId = null;
        await loadTree();
      } catch (err) {
        alert(String(err.message || err));
      }
    }
  });

  window.notetaskGoals = {
    load: loadGoalsView,
    destroy() {
      if (cy) {
        cy.destroy();
        cy = null;
      }
    },
  };
})();
