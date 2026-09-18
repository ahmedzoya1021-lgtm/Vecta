// This runs in your browser. It talks to the Flask backend over the
// /api/... URLs defined in app.py, and updates the page with the results.

const tableBody = document.getElementById("holdings-body");
const form = document.getElementById("add-form");
const briefingBtn = document.getElementById("briefing-btn");
const briefingResult = document.getElementById("briefing-result");

function money(n) {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function renderRow(item) {
  const row = document.createElement("tr");
  row.dataset.id = item.id;
  row.innerHTML = `
    <td>${item.symbol}</td>
    <td>${money(item.price)}</td>
    <td class="row-actions">
      <button class="insight-toggle" data-symbol="${item.symbol}">AI context</button>
      <button class="delete-btn" data-id="${item.id}">Remove</button>
    </td>
  `;
  return row;
}

async function loadWatchlist() {
  const res = await fetch("/api/watchlist");
  const data = await res.json();

  tableBody.innerHTML = "";
  for (const item of data.watchlist) {
    tableBody.appendChild(renderRow(item));
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const symbol = document.getElementById("symbol").value;

  await fetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });

  form.reset();
  loadWatchlist();
});

tableBody.addEventListener("click", async (e) => {
  const target = e.target;
  const row = target.closest("tr");
  const id = target.dataset.id;

  if (target.classList.contains("delete-btn")) {
    const symbol = row.querySelector("td").textContent;
    if (!confirm(`Remove ${symbol} from your watchlist?`)) return;
    await fetch(`/api/watchlist/${id}`, { method: "DELETE" });
    loadWatchlist();
    return;
  }

  if (target.classList.contains("insight-toggle")) {
    const symbol = target.dataset.symbol;
    const existing = row.nextElementSibling;
    if (existing && existing.classList.contains("insight-row")) {
      existing.remove();
      return;
    }

    target.disabled = true;
    target.innerHTML = `<span class="spinner"></span>`;

    const res = await fetch(`/api/insights/${symbol}`);
    const data = await res.json();

    target.disabled = false;
    target.textContent = "AI context";

    const sourcesHtml = (data.sources || [])
      .map((s) => `<a href="${s.url}" target="_blank" rel="noopener">${s.title}</a>`)
      .join(" · ");

    const insightRow = document.createElement("tr");
    insightRow.className = "insight-row";
    insightRow.innerHTML = `
      <td colspan="3">
        ${data.summary}
        ${sourcesHtml ? `<div class="sources">Sources: ${sourcesHtml}</div>` : ""}
      </td>
    `;
    row.after(insightRow);
  }
});

briefingBtn.addEventListener("click", async () => {
  briefingBtn.disabled = true;
  briefingBtn.innerHTML = `<span class="spinner"></span>`;
  briefingResult.textContent = "";

  const res = await fetch("/api/watchlist-briefing");
  const data = await res.json();

  briefingBtn.disabled = false;
  briefingBtn.textContent = "Get briefing";

  const sourcesHtml = (data.sources || [])
    .map((s) => `<a href="${s.url}" target="_blank" rel="noopener">${s.title}</a>`)
    .join(" · ");

  briefingResult.innerHTML = `
    <div>${data.summary}</div>
    ${sourcesHtml ? `<div class="sources">Sources: ${sourcesHtml}</div>` : ""}
  `;
});

loadWatchlist();
