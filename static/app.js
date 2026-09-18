// This runs in your browser. It talks to the Flask backend over the
// /api/... URLs defined in app.py, and updates the page with the results.

const tableBody = document.getElementById("holdings-body");
const totalValueEl = document.getElementById("total-value");
const totalGainEl = document.getElementById("total-gain");
const form = document.getElementById("add-form");
const briefingBtn = document.getElementById("briefing-btn");
const briefingResult = document.getElementById("briefing-result");

let lastData = null;

function money(n) {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function renderRow(h) {
  const row = document.createElement("tr");
  row.dataset.id = h.id;
  row.innerHTML = `
    <td>${h.symbol}</td>
    <td class="cell-shares">${h.shares}</td>
    <td class="cell-cost">${money(h.cost_basis)}</td>
    <td>${money(h.price)}</td>
    <td>${money(h.value)}</td>
    <td class="${h.gain >= 0 ? "positive" : "negative"}">${money(h.gain)}</td>
    <td class="row-actions">
      <button class="insight-toggle" data-symbol="${h.symbol}">AI context</button>
      <button class="edit-btn" data-id="${h.id}">Edit</button>
      <button class="delete-btn" data-id="${h.id}">Remove</button>
    </td>
  `;
  return row;
}

async function loadPortfolio() {
  const res = await fetch("/api/portfolio");
  const data = await res.json();
  lastData = data;

  totalValueEl.textContent = money(data.total_value);
  totalGainEl.textContent = money(data.total_gain);
  totalGainEl.className = "value " + (data.total_gain >= 0 ? "positive" : "negative");

  tableBody.innerHTML = "";
  for (const h of data.holdings) {
    tableBody.appendChild(renderRow(h));
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const symbol = document.getElementById("symbol").value;
  const shares = document.getElementById("shares").value;
  const cost_basis = document.getElementById("cost_basis").value;

  await fetch("/api/holdings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, shares, cost_basis }),
  });

  form.reset();
  loadPortfolio();
});

function enterEditMode(row, holding) {
  row.querySelector(".cell-shares").innerHTML =
    `<input class="edit-input" type="number" step="any" value="${holding.shares}" data-field="shares">`;
  row.querySelector(".cell-cost").innerHTML =
    `<input class="edit-input" type="number" step="any" value="${holding.cost_basis}" data-field="cost_basis">`;
  row.querySelector(".row-actions").innerHTML = `
    <button class="save-btn" data-id="${holding.id}">Save</button>
    <button class="cancel-btn" data-id="${holding.id}">Cancel</button>
  `;
}

tableBody.addEventListener("click", async (e) => {
  const target = e.target;
  const row = target.closest("tr");
  const id = target.dataset.id;

  if (target.classList.contains("delete-btn")) {
    const symbol = row.querySelector("td").textContent;
    if (!confirm(`Remove ${symbol} from your portfolio?`)) return;
    await fetch(`/api/holdings/${id}`, { method: "DELETE" });
    loadPortfolio();
    return;
  }

  if (target.classList.contains("edit-btn")) {
    const holding = lastData.holdings.find((h) => String(h.id) === id);
    enterEditMode(row, holding);
    return;
  }

  if (target.classList.contains("cancel-btn")) {
    loadPortfolio();
    return;
  }

  if (target.classList.contains("save-btn")) {
    const shares = row.querySelector('[data-field="shares"]').value;
    const cost_basis = row.querySelector('[data-field="cost_basis"]').value;
    await fetch(`/api/holdings/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shares, cost_basis }),
    });
    loadPortfolio();
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
      <td colspan="7">
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

  const res = await fetch("/api/portfolio-insight");
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

loadPortfolio();
