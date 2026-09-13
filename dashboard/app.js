/**
 * Customer Intelligence & CLV Engine - Client Application Logic
 */

let globalSummary = null;
let currentCustomersPage = 1;
let currentLimit = 15;
let currentSort = "monetary";
let currentOrder = "desc";
let charts = {};

// Color maps for personas
const PERSONA_COLORS = {
  "Champions (VIP)": "#FBBF24",
  "Loyal Customers": "#10B981",
  "Potential Loyalists": "#38BDF8",
  "Promising New": "#8B5CF6",
  "At-Risk High Spenders": "#F43F5E",
  "Hibernating / Inactive": "#94A3B8",
  "Low Value Occasional": "#64748B",
  "Wholesale / Institutional": "#F97316"
};

const PERSONA_BADGE_CLASSES = {
  "Champions (VIP)": "badge-vip",
  "Loyal Customers": "badge-loyal",
  "Potential Loyalists": "badge-potential",
  "Promising New": "badge-promising",
  "At-Risk High Spenders": "badge-risk",
  "Hibernating / Inactive": "badge-inactive",
  "Low Value Occasional": "badge-inactive",
  "Wholesale / Institutional": "badge-wholesale"
};

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadSummary();
  loadCustomers();
  initTableControls();
  initSimulator();
  initModal();
});

// ==========================================
// Tabs Navigation
// ==========================================
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const targetId = `tab-${tab.dataset.tab}`;
      document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.toggle("active", panel.id === targetId);
      });

      // Resize charts when switching tabs
      Object.values(charts).forEach(c => {
        if (c) c.resize();
      });
    });
  });
}

// ==========================================
// Load Summary & Render Visualizations
// ==========================================
async function loadSummary() {
  try {
    const res = await fetch("/api/summary");
    if (!res.ok) throw new Error("Could not fetch summary data");
    globalSummary = await res.json();

    renderKPIs(globalSummary.kpis);
    renderCharts(globalSummary);
    renderInsights(globalSummary.segments);
    renderSegmentScorecards(globalSummary.segments);
    populatePersonaDropdown(globalSummary.segments);
  } catch (err) {
    console.error("Error loading summary:", err);
  }
}

function renderKPIs(kpis) {
  document.getElementById("kpiTotalRevenue").textContent = `£${kpis.total_revenue.toLocaleString()}`;
  document.getElementById("kpiTotalCustomers").textContent = kpis.total_customers.toLocaleString();
  document.getElementById("kpiAvgAOV").textContent = `£${kpis.avg_aov.toFixed(2)}`;
  document.getElementById("kpiAvgChurn").textContent = `${kpis.avg_churn_risk.toFixed(1)}%`;
  document.getElementById("kpiTotalCLV").textContent = `£${Math.round(kpis.total_projected_clv_12m).toLocaleString()}`;
}

function renderCharts(data) {
  const segments = data.segments;
  const labels = segments.map(s => s.persona);
  const colors = labels.map(l => PERSONA_COLORS[l] || "#A855F7");

  // 1. Revenue Share Donut Chart
  const ctxRev = document.getElementById("chartRevenueShare").getContext("2d");
  charts.revenue = new Chart(ctxRev, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: segments.map(s => s.total_revenue),
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: "#0F172A",
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { color: "#CBD5E1", font: { size: 11, family: "Plus Jakarta Sans" } } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` £${ctx.raw.toLocaleString()} (${segments[ctx.dataIndex].revenue_share}%)`
          }
        }
      },
      cutout: "68%"
    }
  });

  // 2. Customer Share Donut Chart
  const ctxCust = document.getElementById("chartCustomerShare").getContext("2d");
  charts.customers = new Chart(ctxCust, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: segments.map(s => s.count),
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: "#0F172A",
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { color: "#CBD5E1", font: { size: 11, family: "Plus Jakarta Sans" } } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.raw.toLocaleString()} customers (${segments[ctx.dataIndex].percentage}%)`
          }
        }
      },
      cutout: "68%"
    }
  });

  // 3. Projected CLV vs Monetary Bar Chart
  const ctxClv = document.getElementById("chartClvCompare").getContext("2d");
  charts.clv = new Chart(ctxClv, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Avg Spend (£)",
          data: segments.map(s => s.avg_monetary),
          backgroundColor: "rgba(56, 189, 248, 0.75)",
          borderRadius: 6
        },
        {
          label: "Avg Projected 12M CLV (£)",
          data: segments.map(s => Math.round(s.total_clv_12m / s.count)),
          backgroundColor: "rgba(139, 92, 246, 0.85)",
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: "#94A3B8", font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: "#94A3B8", callback: v => `£${v}` }, grid: { color: "rgba(255, 255, 255, 0.05)" } }
      },
      plugins: {
        legend: { labels: { color: "#CBD5E1", font: { family: "Plus Jakarta Sans" } } }
      }
    }
  });

  // 4. 2D PCA Scatter Plot
  if (data.pca_sample && data.pca_sample.length > 0) {
    const ctxPCA = document.getElementById("chartPCA").getContext("2d");
    
    // Group sample points by persona
    const datasetsByPersona = {};
    data.pca_sample.forEach(pt => {
      if (!datasetsByPersona[pt.segment_persona]) {
        datasetsByPersona[pt.segment_persona] = [];
      }
      datasetsByPersona[pt.segment_persona].push({
        x: pt.pca_x,
        y: pt.pca_y,
        id: pt.CustomerID,
        spend: pt.monetary,
        recency: pt.recency,
        churn: pt.churn_risk_score
      });
    });

    const scatterDatasets = Object.keys(datasetsByPersona).map(p => ({
      label: p,
      data: datasetsByPersona[p],
      backgroundColor: PERSONA_COLORS[p] || "#A855F7",
      pointRadius: 4,
      pointHoverRadius: 7
    }));

    charts.pca = new Chart(ctxPCA, {
      type: "scatter",
      data: { datasets: scatterDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: "Principal Component 1 (Monetary & Order Velocity)", color: "#94A3B8" }, grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#64748B" } },
          y: { title: { display: true, text: "Principal Component 2 (Recency Inversion)", color: "#94A3B8" }, grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#64748B" } }
        },
        plugins: {
          legend: { position: "top", labels: { color: "#CBD5E1", font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const pt = ctx.raw;
                return `Customer #${pt.id} | Spend: £${pt.spend} | Recency: ${pt.recency}d | Churn: ${pt.churn}%`;
              }
            }
          }
        }
      }
    });
  }
}

function renderInsights(segments) {
  const container = document.getElementById("insightsList");
  container.innerHTML = "";

  const champions = segments.find(s => s.persona === "Champions (VIP)");
  const atRisk = segments.find(s => s.persona === "At-Risk High Spenders");
  const loyal = segments.find(s => s.persona === "Loyal Customers");
  const inactive = segments.find(s => s.persona.includes("Hibernating"));

  const items = [
    {
      title: "Champions Drive Outsized Value",
      desc: champions ? `${champions.percentage}% of cohort generates £${champions.total_revenue.toLocaleString()} (${champions.revenue_share}% of total sales) with an average basket of £${champions.avg_aov}.` : "",
      style: "gold"
    },
    {
      title: "High-Spender Churn Prevention Alert",
      desc: atRisk ? `${atRisk.count} high-value customers are lapsing with an average recency of ${atRisk.avg_recency} days. Immediate concierge intervention required to protect projected £${atRisk.total_clv_12m.toLocaleString()} CLV.` : "",
      style: "danger"
    },
    {
      title: "Loyalty Expansion Engine",
      desc: loyal ? `${loyal.count} loyal customers average ${loyal.avg_frequency} orders each. Automated category cross-selling and replenishment campaigns can shift ~30% into Champions tier.` : "",
      style: "success"
    }
  ];

  items.forEach(item => {
    const div = document.createElement("div");
    div.className = `insight-box ${item.style}`;
    div.innerHTML = `
      <div class="insight-title">${item.title}</div>
      <div class="insight-desc">${item.desc}</div>
    `;
    container.appendChild(div);
  });
}

function renderSegmentScorecards(segments) {
  const grid = document.getElementById("segmentCardsGrid");
  grid.innerHTML = "";

  segments.forEach(seg => {
    const badgeClass = PERSONA_BADGE_CLASSES[seg.persona] || "badge-promising";
    const card = document.createElement("div");
    card.className = "segment-card";
    card.innerHTML = `
      <div>
        <div class="segment-card-header">
          <h4 class="segment-card-title">${seg.persona}</h4>
          <span class="badge ${badgeClass}">${seg.percentage}% of Base</span>
        </div>
        <div class="segment-metrics-grid">
          <div>
            <div class="seg-stat-label">Total Spend</div>
            <div class="seg-stat-val">£${seg.total_revenue.toLocaleString()}</div>
          </div>
          <div>
            <div class="seg-stat-label">Avg Recency</div>
            <div class="seg-stat-val">${seg.avg_recency} days</div>
          </div>
          <div>
            <div class="seg-stat-label">Avg Orders</div>
            <div class="seg-stat-val">${seg.avg_frequency}</div>
          </div>
          <div>
            <div class="seg-stat-label">Avg Return Rate</div>
            <div class="seg-stat-val">${seg.avg_return_rate}%</div>
          </div>
          <div>
            <div class="seg-stat-label">Avg Churn Risk</div>
            <div class="seg-stat-val ${seg.avg_churn_risk > 60 ? 'text-danger' : 'text-success'}">${seg.avg_churn_risk}%</div>
          </div>
          <div>
            <div class="seg-stat-label">12M Total CLV</div>
            <div class="seg-stat-val text-success">£${seg.total_clv_12m.toLocaleString()}</div>
          </div>
        </div>
      </div>
      <div class="strategy-callout">
        <strong>Strategic Directive:</strong>
        ${seg.recommended_action}
      </div>
    `;
    grid.appendChild(card);
  });
}

function populatePersonaDropdown(segments) {
  const select = document.getElementById("personaFilter");
  segments.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.persona;
    opt.textContent = `${s.persona} (${s.count})`;
    select.appendChild(opt);
  });
}

// ==========================================
// Customer Directory & Table Logic
// ==========================================
async function loadCustomers() {
  const search = document.getElementById("customerSearchInput").value;
  const persona = document.getElementById("personaFilter").value;
  const risk = document.getElementById("riskFilter").value;
  const sortBy = document.getElementById("sortBy").value;

  const url = `/api/customers?search=${encodeURIComponent(search)}&persona=${encodeURIComponent(persona)}&risk=${encodeURIComponent(risk)}&sort_by=${sortBy}&order=${currentOrder}&page=${currentCustomersPage}&limit=${currentLimit}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch customers");
    const data = await res.json();

    renderCustomerTable(data.customers);
    renderPagination(data);
  } catch (err) {
    console.error("Error loading customers:", err);
  }
}

function renderCustomerTable(customers) {
  const tbody = document.getElementById("customersTableBody");
  tbody.innerHTML = "";

  if (!customers || customers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center py-6 text-muted">No customers found matching filter criteria.</td></tr>`;
    return;
  }

  customers.forEach(c => {
    const tr = document.createElement("tr");
    const badgeClass = PERSONA_BADGE_CLASSES[c.segment_persona] || "badge-promising";
    const riskClass = c.churn_risk_score >= 65 ? "text-danger" : (c.churn_risk_score >= 35 ? "text-warning" : "text-success");

    tr.innerHTML = `
      <td class="customer-id-cell">#${c.CustomerID}</td>
      <td><span class="badge ${badgeClass}">${c.segment_persona}</span></td>
      <td><strong>£${c.monetary.toLocaleString()}</strong></td>
      <td>${c.frequency}</td>
      <td>${c.recency}d</td>
      <td>£${c.aov}</td>
      <td>${c.return_rate}%</td>
      <td class="${riskClass}"><strong>${c.churn_risk_score}%</strong></td>
      <td class="text-success"><strong>£${c.projected_clv_12m.toLocaleString()}</strong></td>
      <td>
        <button class="btn btn-sm btn-outline btn-view-profile" data-customer='${JSON.stringify(c).replace(/'/g, "&apos;")}'>
          View
        </button>
      </td>
    `;

    // Row click opens modal
    tr.addEventListener("click", (e) => {
      if (!e.target.closest(".btn-view-profile")) {
        openCustomerModal(c);
      }
    });

    const btn = tr.querySelector(".btn-view-profile");
    btn.addEventListener("click", () => openCustomerModal(c));

    tbody.appendChild(tr);
  });
}

function renderPagination(data) {
  const info = document.getElementById("paginationInfo");
  const start = (data.page - 1) * data.limit + 1;
  const end = Math.min(data.total, data.page * data.limit);
  info.textContent = `Showing ${data.total > 0 ? start : 0} to ${end} of ${data.total.toLocaleString()} customers`;

  document.getElementById("currentPageNum").textContent = `Page ${data.page} of ${Math.max(1, data.total_pages)}`;
  document.getElementById("btnPrevPage").disabled = (data.page <= 1);
  document.getElementById("btnNextPage").disabled = (data.page >= data.total_pages);
}

function initTableControls() {
  const searchInput = document.getElementById("customerSearchInput");
  let debounceTimeout = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      currentCustomersPage = 1;
      loadCustomers();
    }, 300);
  });

  document.getElementById("personaFilter").addEventListener("change", () => {
    currentCustomersPage = 1;
    loadCustomers();
  });

  document.getElementById("riskFilter").addEventListener("change", () => {
    currentCustomersPage = 1;
    loadCustomers();
  });

  document.getElementById("sortBy").addEventListener("change", (e) => {
    currentSort = e.target.value;
    loadCustomers();
  });

  document.getElementById("btnPrevPage").addEventListener("click", () => {
    if (currentCustomersPage > 1) {
      currentCustomersPage--;
      loadCustomers();
    }
  });

  document.getElementById("btnNextPage").addEventListener("click", () => {
    currentCustomersPage++;
    loadCustomers();
  });

  // Export buttons
  document.getElementById("btnExportAll").addEventListener("click", () => {
    window.location.href = "/api/export?persona=All";
  });

  document.getElementById("btnExportFiltered").addEventListener("click", () => {
    const persona = document.getElementById("personaFilter").value;
    window.location.href = `/api/export?persona=${encodeURIComponent(persona)}`;
  });
}

// ==========================================
// Customer Profile Modal
// ==========================================
function initModal() {
  const backdrop = document.getElementById("customerModalBackdrop");
  const closeBtn = document.getElementById("btnModalClose");

  closeBtn.addEventListener("click", () => backdrop.classList.remove("active"));
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) backdrop.classList.remove("active");
  });
}

function openCustomerModal(c) {
  document.getElementById("modalCustomerId").textContent = `Customer #${c.CustomerID}`;
  const badge = document.getElementById("modalPersonaBadge");
  badge.textContent = c.segment_persona;
  badge.className = `badge ${PERSONA_BADGE_CLASSES[c.segment_persona] || 'badge-vip'}`;

  document.getElementById("modalSpend").textContent = `£${c.monetary.toLocaleString()}`;
  document.getElementById("modalOrders").textContent = `${c.frequency} orders (${c.items_count || c.frequency * 5} units)`;
  document.getElementById("modalRecency").textContent = `${c.recency} days ago`;
  document.getElementById("modalAOV").textContent = `£${c.aov}`;
  document.getElementById("modalTenure").textContent = `${c.tenure_days || '-'} days`;
  document.getElementById("modalReturnRate").textContent = `${c.return_rate}%`;
  document.getElementById("modalChurnRisk").textContent = `${c.churn_risk_score}%`;
  document.getElementById("modalCLV").textContent = `£${c.projected_clv_12m.toLocaleString()}`;
  document.getElementById("modalActionText").textContent = c.recommended_action || "Target with personalized offers.";

  document.getElementById("customerModalBackdrop").classList.add("active");
}

// ==========================================
// Predictive Simulator
// ==========================================
function initSimulator() {
  const form = document.getElementById("simulatorForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      recency: parseFloat(document.getElementById("simRecency").value),
      frequency: parseFloat(document.getElementById("simFrequency").value),
      monetary: parseFloat(document.getElementById("simMonetary").value),
      tenure_days: parseFloat(document.getElementById("simTenure").value),
      return_rate: parseFloat(document.getElementById("simReturnRate").value)
    };

    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Simulation request failed");
      const result = await res.json();

      const badge = document.getElementById("simPersonaBadge");
      badge.textContent = result.persona;
      badge.className = `badge ${PERSONA_BADGE_CLASSES[result.persona] || 'badge-promising'}`;

      document.getElementById("simChurnRisk").textContent = `${result.churn_risk_score}%`;
      document.getElementById("simChurnBar").style.width = `${result.churn_risk_score}%`;
      document.getElementById("simClv12M").textContent = `£${result.projected_clv_12m.toLocaleString()}`;
      document.getElementById("simClv6M").textContent = `£${result.projected_clv_6m.toLocaleString()}`;
      document.getElementById("simAOV").textContent = `£${result.aov}`;
      document.getElementById("simRecommendation").textContent = result.recommended_action;
    } catch (err) {
      console.error("Simulation error:", err);
      alert("Error calculating prediction. Check server status.");
    }
  });

  // Run once initially
  form.dispatchEvent(new Event("submit"));
}
