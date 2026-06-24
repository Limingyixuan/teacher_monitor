const DATA_URL = "./data/latest_jobs.json";
const FAVORITES_KEY = "baoding-teacher-favorites";
const EXCLUSIONS_KEY = "baoding-teacher-exclusions";
const EXCLUSION_OPTIONS = [
  "民办", "私立", "培训机构", "代课", "合同制", "劳务派遣",
  "人事代理", "购买服务", "临聘", "编外", "校聘", "派遣制",
  "见习", "实习", "备案制", "控制数", "员额制", "聘用制",
];

const state = {
  jobs: [],
  filter: "all",
  region: "all",
  level: "all",
  sourceType: "all",
  query: "",
  favorites: new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]")),
  exclusions: new Set(JSON.parse(localStorage.getItem(EXCLUSIONS_KEY) || "[]")),
};

const elements = {
  list: document.querySelector("#jobList"),
  template: document.querySelector("#jobTemplate"),
  empty: document.querySelector("#emptyState"),
  updateText: document.querySelector("#updateText"),
  total: document.querySelector("#totalCount"),
  confirmed: document.querySelector("#confirmedCount"),
  review: document.querySelector("#reviewCount"),
  resultCount: document.querySelector("#resultCount"),
  search: document.querySelector("#searchInput"),
  refresh: document.querySelector("#refreshButton"),
  chips: document.querySelector("#filterChips"),
  regionChips: document.querySelector("#regionChips"),
  selectedRegionText: document.querySelector("#selectedRegionText"),
  levelChips: document.querySelector("#levelChips"),
  selectedLevelText: document.querySelector("#selectedLevelText"),
  sourceType: document.querySelector("#sourceTypeSelect"),
  excludeCount: document.querySelector("#excludeCount"),
  excludeOptions: document.querySelector("#excludeOptions"),
  dialog: document.querySelector("#helpDialog"),
  filterDialog: document.querySelector("#filterDialog"),
};

const labels = {
  confirmed: ["明确事业编", ""],
  likely: ["事业单位招聘", "likely"],
  uncertain: ["编制性质待核实", "review"],
  needs_review: ["需人工核实", "review"],
};

function formatTime(value) {
  if (!value) return "更新时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return `更新于 ${value}`;
  return `更新于 ${new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)}`;
}

function saveFavorites() {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites]));
}

function saveExclusions() {
  localStorage.setItem(EXCLUSIONS_KEY, JSON.stringify([...state.exclusions]));
  elements.excludeCount.textContent = state.exclusions.size;
}

function matchesFilter(job) {
  if (state.filter === "all") return true;
  if (state.filter === "favorite") return state.favorites.has(job.url);
  if (state.filter === "review") {
    return ["uncertain", "needs_review"].includes(job.classification);
  }
  return job.classification === state.filter;
}

function matchesRegion(job) {
  return state.region === "all" || (job.regions || []).includes(state.region);
}

function matchesLevel(job) {
  const levels = job.school_levels || ["学段待核实"];
  if (state.level === "all") return true;
  if (state.level === "both") return levels.includes("初中") && levels.includes("高中");
  if (state.level === "unknown") {
    return levels.some(level => ["学段待核实", "中学未细分"].includes(level));
  }
  return levels.includes(state.level);
}

function matchesSource(job) {
  return state.sourceType === "all" || job.source_type === state.sourceType;
}

function passesExclusions(job) {
  return !(job.employment_terms || []).some(term => state.exclusions.has(term));
}

function matchesQuery(job) {
  const query = state.query.trim().toLowerCase();
  if (!query) return true;
  const haystack = [
    job.title,
    job.source,
    ...(job.matched_terms || []),
  ].join(" ").toLowerCase();
  return haystack.includes(query);
}

function render() {
  const jobs = state.jobs.filter(job =>
    matchesFilter(job) &&
    matchesQuery(job) &&
    matchesRegion(job) &&
    matchesLevel(job) &&
    matchesSource(job) &&
    passesExclusions(job)
  );
  elements.list.replaceChildren();
  elements.resultCount.textContent = `${jobs.length} 条`;
  elements.empty.classList.toggle("hidden", jobs.length !== 0);

  jobs.forEach((job, index) => {
    const fragment = elements.template.content.cloneNode(true);
    const card = fragment.querySelector(".job-card");
    const link = fragment.querySelector(".job-link");
    const badge = fragment.querySelector(".badge");
    const favorite = fragment.querySelector(".favorite-button");
    const sourceBadge = fragment.querySelector(".source-badge");
    const [label, badgeClass] = labels[job.classification] || labels.needs_review;

    card.style.animationDelay = `${Math.min(index * 45, 250)}ms`;
    badge.textContent = label;
    if (badgeClass) badge.classList.add(badgeClass);
    sourceBadge.textContent = job.source_type === "aggregator" ? "第三方线索" : "官方来源";
    if (job.source_type === "aggregator") sourceBadge.classList.add("aggregator");
    link.href = job.url;
    fragment.querySelector(".job-title").textContent = job.title;
    fragment.querySelector(".job-date").textContent = job.date || "日期未识别";
    fragment.querySelector(".job-region").textContent = (job.regions || ["地区待核实"]).join("、");
    fragment.querySelector(".job-level").textContent =
      (job.school_levels || ["学段待核实"]).join("＋");
    fragment.querySelector(".job-source").textContent = job.source;

    const terms = fragment.querySelector(".terms");
    [...new Set([...(job.employment_terms || []), ...(job.matched_terms || [])])]
      .slice(0, 6).forEach(term => {
      const tag = document.createElement("span");
      tag.className = "term";
      tag.textContent = term;
      terms.append(tag);
    });

    const saved = state.favorites.has(job.url);
    favorite.textContent = saved ? "★" : "☆";
    favorite.classList.toggle("saved", saved);
    favorite.setAttribute("aria-label", saved ? "取消收藏" : "收藏公告");
    favorite.addEventListener("click", () => {
      if (state.favorites.has(job.url)) state.favorites.delete(job.url);
      else state.favorites.add(job.url);
      saveFavorites();
      render();
    });

    elements.list.append(fragment);
  });
}

function populateRegions() {
  const current = state.region;
  const regions = [...new Set(state.jobs.flatMap(job => job.regions || []))]
    .sort((a, b) => a.localeCompare(b, "zh-CN"));
  if (current !== "all" && !regions.includes(current)) state.region = "all";
  elements.regionChips.replaceChildren();
  ["all", ...regions].forEach(region => {
    const button = document.createElement("button");
    button.className = "region-chip";
    button.dataset.region = region;
    button.textContent = region === "all" ? "全部地区" : region;
    button.classList.toggle("active", region === state.region);
    elements.regionChips.append(button);
  });
  elements.selectedRegionText.textContent =
    state.region === "all" ? "全部地区" : state.region;
}

function buildExclusionOptions() {
  elements.excludeOptions.replaceChildren();
  EXCLUSION_OPTIONS.forEach(term => {
    const label = document.createElement("label");
    label.className = "exclude-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = term;
    input.checked = state.exclusions.has(term);
    const text = document.createElement("span");
    text.textContent = term;
    label.append(input, text);
    elements.excludeOptions.append(label);
  });
  elements.excludeCount.textContent = state.exclusions.size;
}

function updateSummary() {
  elements.total.textContent = state.jobs.length;
  elements.confirmed.textContent =
    state.jobs.filter(job => job.classification === "confirmed").length;
  elements.review.textContent =
    state.jobs.filter(job => ["uncertain", "needs_review"].includes(job.classification)).length;
}

async function loadJobs({ fresh = false } = {}) {
  elements.refresh.classList.add("loading");
  try {
    const suffix = fresh ? `?t=${Date.now()}` : "";
    const response = await fetch(DATA_URL + suffix, { cache: fresh ? "reload" : "default" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.jobs = Array.isArray(data.items) ? data.items : [];
    const failureCount = Array.isArray(data.source_failures) ? data.source_failures.length : 0;
    elements.updateText.textContent =
      `${formatTime(data.generated_at)}${failureCount ? ` · ${failureCount} 个来源暂不可用` : ""}`;
    updateSummary();
    populateRegions();
    render();
  } catch (error) {
    elements.updateText.textContent = navigator.onLine
      ? "读取失败，请稍后刷新"
      : "当前离线，显示已缓存内容";
    console.error(error);
  } finally {
    elements.refresh.classList.remove("loading");
  }
}

elements.search.addEventListener("input", event => {
  state.query = event.target.value;
  render();
});

elements.chips.addEventListener("click", event => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  elements.chips.querySelectorAll(".chip").forEach(chip => {
    chip.classList.toggle("active", chip === button);
  });
  render();
});

elements.refresh.addEventListener("click", () => loadJobs({ fresh: true }));
elements.regionChips.addEventListener("click", event => {
  const button = event.target.closest("[data-region]");
  if (!button) return;
  state.region = button.dataset.region;
  elements.regionChips.querySelectorAll(".region-chip").forEach(chip => {
    chip.classList.toggle("active", chip === button);
  });
  elements.selectedRegionText.textContent =
    state.region === "all" ? "全部地区" : state.region;
  render();
});
elements.levelChips.addEventListener("click", event => {
  const button = event.target.closest("[data-level]");
  if (!button) return;
  state.level = button.dataset.level;
  elements.levelChips.querySelectorAll(".level-chip").forEach(chip => {
    chip.classList.toggle("active", chip === button);
  });
  const labels = {
    all: "全部学段",
    初中: "初中",
    高中: "高中",
    both: "初高中",
    unknown: "学段待核实",
  };
  elements.selectedLevelText.textContent = labels[state.level];
  render();
});
elements.sourceType.addEventListener("change", event => {
  state.sourceType = event.target.value;
  render();
});
document.querySelector("#installHelp").addEventListener("click", () => elements.dialog.showModal());
document.querySelector("#closeDialog").addEventListener("click", () => elements.dialog.close());
elements.dialog.addEventListener("click", event => {
  if (event.target === elements.dialog) elements.dialog.close();
});
document.querySelector("#excludeSettings").addEventListener("click", () => {
  buildExclusionOptions();
  elements.filterDialog.showModal();
});
document.querySelector("#closeFilterDialog").addEventListener("click", () => elements.filterDialog.close());
document.querySelector("#clearExclusions").addEventListener("click", () => {
  elements.excludeOptions.querySelectorAll("input").forEach(input => { input.checked = false; });
});
document.querySelector("#applyExclusions").addEventListener("click", () => {
  state.exclusions = new Set(
    [...elements.excludeOptions.querySelectorAll("input:checked")].map(input => input.value)
  );
  saveExclusions();
  elements.filterDialog.close();
  render();
});
elements.filterDialog.addEventListener("click", event => {
  if (event.target === elements.filterDialog) elements.filterDialog.close();
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
}

buildExclusionOptions();
loadJobs();
