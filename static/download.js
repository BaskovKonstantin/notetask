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
    .then((r) => r.json())
    .then((data) => {
      const items = data.items || [];
      root.innerHTML = items
        .map((item) => {
          if (item.available) {
            return `<a class="btn download-btn" href="${base}${item.url}">${item.label} — скачать (${fmtSize(item.size)})</a>
              <p class="download-hint">${item.hint}</p>`;
          }
          return `<button type="button" class="btn download-btn" disabled>${item.label} — скоро</button>
            <p class="download-hint">${item.hint}</p>`;
        })
        .join("");
    })
    .catch(() => {
      root.textContent = "Не удалось получить список файлов";
    });
})();
