/* ============================================================
   Linux 发行版图鉴 — 交互逻辑
   数据驱动渲染 · 家族筛选 · 搜索 · 详情弹窗 · stagger 动画
   ============================================================ */
(() => {
  "use strict";

  const DATA_URL = "assets/data/distros.json";
  const LOGOS_URL = "assets/data/logos.json";
  const LOGO_DIR = "assets/logos";

  const state = {
    families: {},
    distros: [],
    logos: {},          // id -> 本地文件名
    familyFilter: "all",
    search: "",
    byId: new Map(),
    childrenOf: new Map(), // parentId -> [distroIds]
  };

  const el = {
    grid: document.getElementById("grid"),
    empty: document.getElementById("empty"),
    search: document.getElementById("search"),
    familyNav: document.getElementById("family-nav"),
    resultCount: document.getElementById("result-count"),
    statDistros: document.getElementById("stat-distros"),
    statFamilies: document.getElementById("stat-families"),
    statBranches: document.getElementById("stat-branches"),
    modal: document.getElementById("modal"),
    modalBody: document.getElementById("modal-body"),
    modalBackdrop: document.getElementById("modal-backdrop"),
    modalClose: document.getElementById("modal-close"),
  };

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- 数据加载 ---------- */
  async function loadData() {
    const [dataRes, logosRes] = await Promise.all([
      fetch(DATA_URL).then(r => r.json()),
      fetch(LOGOS_URL).then(r => r.json()).catch(() => ({})),
    ]);
    state.families = dataRes.families;
    state.distros = dataRes.distros;
    state.logos = logosRes;
    for (const d of state.distros) {
      state.byId.set(d.id, d);
      if (d.parent) {
        if (!state.childrenOf.has(d.parent)) state.childrenOf.set(d.parent, []);
        state.childrenOf.get(d.parent).push(d.id);
      }
    }
    renderStats();
    renderFamilyNav();
    render();
  }

  /* ---------- 统计 ---------- */
  function renderStats() {
    el.statDistros.textContent = state.distros.length;
    el.statFamilies.textContent = Object.keys(state.families).length;
    let branches = 0;
    for (const kids of state.childrenOf.values()) branches += kids.length;
    el.statBranches.textContent = branches;
  }

  /* ---------- 家族导航 ---------- */
  function renderFamilyNav() {
    const counts = {};
    for (const d of state.distros) counts[d.family] = (counts[d.family] || 0) + 1;

    const btn = (id, label, count, color) => {
      const b = document.createElement("button");
      b.className = "family-btn" + (state.familyFilter === id ? " active" : "");
      b.dataset.family = id;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", state.familyFilter === id ? "true" : "false");
      b.innerHTML = `
        <span class="family-dot" style="color:${color || "var(--accent)"}"></span>
        <span class="family-name">${label}</span>
        <span class="family-count">${count}</span>`;
      b.addEventListener("click", () => {
        state.familyFilter = id;
        renderFamilyNav();
        render();
      });
      return b;
    };

    el.familyNav.innerHTML = "";
    el.familyNav.appendChild(btn("all", "全部发行版", state.distros.length, "var(--accent)"));
    for (const [id, fam] of Object.entries(state.families)) {
      if (counts[id]) el.familyNav.appendChild(btn(id, fam.name, counts[id], fam.color));
    }
  }

  /* ---------- 过滤 ---------- */
  function filtered() {
    const q = state.search.trim().toLowerCase();
    return state.distros.filter(d => {
      if (state.familyFilter !== "all" && d.family !== state.familyFilter) return false;
      if (!q) return true;
      const hay = [d.name, d.tagline, d.desc, d.id, ...(d.tags || [])].join(" ").toLowerCase();
      return q.split(/\s+/).every(part => hay.includes(part));
    });
  }

  /* ---------- Logo 辅助 ---------- */
  function logoUrl(d) {
    const file = state.logos[d.id];
    return file ? `${LOGO_DIR}/${file}` : null;
  }
  function logoHtml(d, cls) {
    const url = logoUrl(d);
    const famColor = (state.families[d.family] || {}).color || "var(--accent)";
    if (url) {
      return `<div class="${cls}" style="--fam-color:${famColor}">
        <img src="${url}" alt="${d.name} logo" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'fallback',textContent:'${d.name.charAt(0).toUpperCase()}'}))">
      </div>`;
    }
    return `<div class="${cls}" style="--fam-color:${famColor}">
      <span class="fallback">${d.name.charAt(0).toUpperCase()}</span>
    </div>`;
  }

  /* ---------- 卡片渲染（stagger 入场） ---------- */
  function render() {
    const list = filtered();
    el.resultCount.textContent = `${list.length} / ${state.distros.length} 个发行版`;
    el.empty.hidden = list.length > 0;

    const frag = document.createDocumentFragment();
    list.forEach((d, i) => {
      const fam = state.families[d.family] || {};
      const card = document.createElement("article");
      card.className = "card";
      card.style.setProperty("--fam-color", fam.color || "var(--accent)");
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `查看 ${d.name} 详情`);
      card.innerHTML = `
        ${logoHtml(d, "card-logo")}
        <span class="card-fam">${fam.name || d.family}</span>
        <div class="card-name">${d.name}</div>
        <div class="card-tagline">${d.tagline || ""}</div>
        <div class="card-tags">${(d.tags || []).slice(0, 3).map(t => `<span class="tag">${t}</span>`).join("")}</div>`;
      card.addEventListener("click", () => openModal(d.id));
      card.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openModal(d.id); }
      });
      frag.appendChild(card);

      // 入场：下一帧加 visible，stagger 间隔 40ms（总时长限制在 ~600ms 内）
      const delay = Math.min(i, 14) * 40;
      setTimeout(() => card.classList.add("visible"), reducedMotion ? 0 : delay);
    });
    el.grid.innerHTML = "";
    el.grid.appendChild(frag);
  }

  /* ---------- 详情弹窗 ---------- */
  function bloodlineHtml(d) {
    const parts = [];
    // 父链
    const chain = [];
    let cur = d;
    while (cur.parent && state.byId.has(cur.parent)) {
      chain.unshift(cur.parent);
      cur = state.byId.get(cur.parent);
    }
    for (const pid of chain) {
      const p = state.byId.get(pid);
      parts.push(`<span class="node">${p.name}</span>`);
      parts.push(`<span class="arrow">→</span>`);
    }
    parts.push(`<span class="node" style="--fam-color:${(state.families[d.family] || {}).color || "var(--accent)"}">${d.name}</span>`);

    // 子分支
    const kids = (state.childrenOf.get(d.id) || [])
      .map(id => state.byId.get(id))
      .filter(Boolean);
    if (kids.length) {
      parts.push(`<span class="arrow">→</span>`);
      kids.forEach((k, i) => {
        parts.push(`<span class="node muted">${k.name}</span>`);
        if (i < kids.length - 1) parts.push(`<span class="arrow">·</span>`);
      });
    }
    return `<div class="bloodline">${parts.join("")}</div>`;
  }

  function openModal(id) {
    const d = state.byId.get(id);
    if (!d) return;
    const fam = state.families[d.family] || {};
    const url = d.url ? `<a class="modal-link" href="${d.url}" target="_blank" rel="noopener noreferrer">↗ 访问官方网站 ${d.url.replace(/^https?:\/\//, "")}</a>` : "";

    el.modalBody.innerHTML = `
      <div class="modal-header">
        ${logoHtml(d, "modal-logo")}
        <div>
          <div class="modal-title" id="modal-name">${d.name}</div>
          <div class="modal-tagline">${d.tagline || ""}</div>
          <span class="modal-fam" style="--fam-color:${fam.color || "var(--accent)"}">${fam.name || d.family}</span>
        </div>
      </div>
      <p class="modal-desc">${d.desc}</p>
      <div class="modal-section">
        <h3>血统 / 分支</h3>
        ${bloodlineHtml(d)}
      </div>
      <div class="modal-section">
        <h3>特点</h3>
        <div class="modal-tags">${(d.tags || []).map(t => `<span class="tag">${t}</span>`).join("")}</div>
      </div>
      ${url ? `<div class="modal-section">${url}</div>` : ""}`;

    el.modal.hidden = false;
    el.modalBackdrop.hidden = false;
    requestAnimationFrame(() => el.modal.classList.add("open"));
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    el.modal.classList.remove("open");
    document.body.style.overflow = "";
    setTimeout(() => {
      el.modal.hidden = true;
      el.modalBackdrop.hidden = true;
    }, reducedMotion ? 0 : 200);
  }

  /* ---------- 事件绑定 ---------- */
  el.search.addEventListener("input", e => {
    state.search = e.target.value;
    render();
  });

  el.modalClose.addEventListener("click", closeModal);
  el.modalBackdrop.addEventListener("click", closeModal);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !el.modal.hidden) closeModal();
  });

  /* ---------- 启动 ---------- */
  loadData().catch(err => {
    console.error("数据加载失败:", err);
    el.grid.innerHTML = `<div class="empty-state"><p class="mono">$ sudo mount --bind reality</p><p>数据加载失败，请检查静态资源是否完整。</p></div>`;
  });
})();
