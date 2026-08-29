(function () {
  const base = window.NOTETASK_BASE || "";
  const root = document.getElementById("download-list");
  if (!root) return;

  function fmtSize(n) {
    if (!n) return "";
    if (n < 1024 * 1024) return `${Math.round(n / 1024)} КБ`;
    return `${(n / (1024 * 1024)).toFixed(1)} МБ`;
  }

  fetch(`${base}/api/downloads`)
    .then((r) => {
      if (!r.ok) throw new Error("list");
      return r.json();
    })
    .then((data) => {
      const items = data.items || [];
      if (!items.length) {
        root.textContent = "Файлы пока не опубликованы";
        return;
      }
      root.innerHTML = items
        .map((item) => {
          if (item.available) {
            const href = `${base}${item.url}`;
            const lan = `http://192.168.0.6:8100${item.url}`;
            return `<a class="btn download-btn" href="${href}" download="${item.filename}">${item.label} — скачать (${fmtSize(item.size)})</a>
              <p class="download-hint">${item.hint}</p>
              <p class="download-hint">Домашний Wi‑Fi не тянет? <a href="${lan}">Прямая ссылка LAN</a></p>`;
          }
          return `<button type="button" class="btn download-btn" disabled>${item.label} — скоро</button>
            <p class="download-hint">${item.hint}</p>`;
        })
        .join("");
    })
    .catch(() => {
      root.innerHTML =
        'Не удалось получить список. С домашнего Wi‑Fi открой <a href="http://192.168.0.6:8100/download">http://192.168.0.6:8100/download</a>';
    });
})();
