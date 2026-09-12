// ---- Tabs ----
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

function loadingHtml(msg) {
  return `<div class="loading">${msg}</div>`;
}

function errorHtml(msg) {
  return `<div class="error-msg">${msg}</div>`;
}

function demoBannerHtml(msg) {
  return `<div class="demo-banner">⚠️ Demo mode — ${msg}</div>`;
}

// ---- Listing Explorer ----
async function runExplorer() {
  const raw = document.getElementById("explorer-input").value;
  const urls = raw.split("\n").map(s => s.trim()).filter(Boolean);
  const out = document.getElementById("explorer-results");
  if (!urls.length) { out.innerHTML = errorHtml("Paste at least one listing URL."); return; }

  out.innerHTML = loadingHtml(`Fetching ${urls.length} listing(s)...`);
  try {
    const res = await fetch("/api/listing/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    const data = await res.json();
    out.innerHTML = "";
    const demoItem = data.results.find(item => item.demo_notice);
    if (demoItem) out.appendChild(el(demoBannerHtml(demoItem.demo_notice)));
    data.results.forEach(item => out.appendChild(renderListingCard(item)));
  } catch (e) {
    out.innerHTML = errorHtml("Request failed: " + e.message);
  }
}

function renderListingCard(item) {
  if (item.error) {
    return el(`<div class="card"><strong>${item.url || "Unknown URL"}</strong>${errorHtml(item.error)}</div>`);
  }
  const est = item.estimated_sales;
  const estText = est ? `${est.low.toLocaleString()}–${est.high.toLocaleString()} (est. ~${est.mid.toLocaleString()})` : "n/a";
  const tags = (item.tags || []).map(t => `<span class="tag-chip">${t}</span>`).join("");

  return el(`
    <div class="card">
      <h3><a href="${item.url}" target="_blank">${item.title || "Untitled listing"}</a></h3>
      <div class="meta-row">
        <span><strong>Price:</strong> ${item.price ? item.price + " " + (item.currency || "") : "n/a"}</span>
        <span><strong>Reviews:</strong> ${item.reviews ?? "n/a"}</span>
        <span><strong>Rating:</strong> ${item.rating ?? "n/a"}</span>
        <span><strong>Favorites:</strong> ${item.favorites ?? "n/a"}</span>
        <span><strong>Shop:</strong> ${item.shop_name ?? "n/a"}</span>
      </div>
      <div class="meta-row"><span><strong>Est. sales:</strong> ${estText}</span></div>
      ${tags ? `<div style="margin-top:10px;">${tags}</div>` : ""}
    </div>
  `);
}

// ---- Keyword Finder ----
async function runKeyword() {
  const keyword = document.getElementById("keyword-input").value.trim();
  const out = document.getElementById("keyword-results");
  if (!keyword) { out.innerHTML = errorHtml("Enter a keyword."); return; }

  out.innerHTML = loadingHtml(`Searching Etsy for "${keyword}"...`);
  try {
    const res = await fetch("/api/keyword", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword }),
    });
    const data = await res.json();
    if (data.error) { out.innerHTML = errorHtml(data.error); return; }

    const s = data.stats;
    const statsCard = el(`
      <div class="card">
        <h3>Competition snapshot</h3>
        <table class="stats-table">
          <tr><td>Results shown</td><td>${s.result_count_shown}</td></tr>
          <tr><td>Average price</td><td>${s.avg_price ?? "n/a"}</td></tr>
          <tr><td>Median price</td><td>${s.median_price ?? "n/a"}</td></tr>
          <tr><td>Price range</td><td>${s.min_price ?? "n/a"} – ${s.max_price ?? "n/a"}</td></tr>
        </table>
      </div>
    `);

    out.innerHTML = "";
    if (data.demo_notice) out.appendChild(el(demoBannerHtml(data.demo_notice)));
    out.appendChild(statsCard);
    data.listings.forEach(l => {
      out.appendChild(el(`
        <div class="card">
          <h3><a href="${l.url}" target="_blank">${l.title || "Untitled"}</a></h3>
          <div class="meta-row">
            <span><strong>Price:</strong> ${l.price || "n/a"}</span>
            <span><strong>Shop:</strong> ${l.shop || "n/a"}</span>
          </div>
        </div>
      `));
    });
  } catch (e) {
    out.innerHTML = errorHtml("Request failed: " + e.message);
  }
}

// ---- Shop Analyzer ----
async function runShop() {
  const shopName = document.getElementById("shop-input").value.trim();
  const out = document.getElementById("shop-results");
  if (!shopName) { out.innerHTML = errorHtml("Enter a shop name."); return; }

  out.innerHTML = loadingHtml(`Analyzing shop "${shopName}"...`);
  try {
    const res = await fetch("/api/shop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shop_name: shopName }),
    });
    const data = await res.json();
    if (data.error) { out.innerHTML = errorHtml(data.error); return; }

    out.innerHTML = "";
    if (data.demo_notice) out.appendChild(el(demoBannerHtml(data.demo_notice)));
    out.appendChild(el(`
      <div class="card">
        <h3><a href="${data.shop_url}" target="_blank">${data.shop_name}</a></h3>
        <div class="meta-row">
          <span><strong>Reported sales:</strong> ${data.total_sales_reported ?? "n/a"}</span>
          <span><strong>Listings found:</strong> ${data.listing_count_found}</span>
        </div>
      </div>
    `));
    data.listing_urls.forEach(u => {
      out.appendChild(el(`<div class="card"><a href="${u}" target="_blank">${u}</a></div>`));
    });
  } catch (e) {
    out.innerHTML = errorHtml("Request failed: " + e.message);
  }
}

// ---- Listing Optimizer ----
async function runOptimizer() {
  const url = document.getElementById("optimizer-input").value.trim();
  const out = document.getElementById("optimizer-results");
  if (!url) { out.innerHTML = errorHtml("Enter a listing URL."); return; }

  out.innerHTML = loadingHtml("Scoring listing...");
  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (data.error) { out.innerHTML = errorHtml(data.error); return; }

    const r = data.report;
    const checksHtml = r.checks.map(c => `
      <div class="check-row">
        <span>${c.check}: ${c.detail}</span>
        <span class="${c.pass ? "check-pass" : "check-fail"}">${c.pass ? "✓" : "✗"}</span>
      </div>
    `).join("");

    out.innerHTML = "";
    if (data.demo_notice) out.appendChild(el(demoBannerHtml(data.demo_notice)));
    out.appendChild(el(`
      <div class="card">
        <h3>${data.listing.title || "Untitled listing"}</h3>
        <div class="score-badge">${r.percent}%</div>
        <p class="hint" style="margin-top:4px;">${r.score} / ${r.max_score} points</p>
        <div style="margin-top:10px;">${checksHtml}</div>
      </div>
    `));
  } catch (e) {
    out.innerHTML = errorHtml("Request failed: " + e.message);
  }
}
