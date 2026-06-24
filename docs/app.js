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
  months: "all",
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
  timeChips: document.querySelector("#timeChips"),
  selectedTimeText: document.querySelector("#selectedTimeText"),
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

const SEARCH_ALIASES = {
  北师大: ["北京师范大学", "北师大"],
  北师: ["北京师范大学", "北师"],
  事业编: ["事业编制", "事业单位", "事业编"],
  教编: ["教师", "事业编制", "教编"],
  中学: ["初中", "高中", "中学"],
  政治: ["政治", "思想政治", "道德与法治"],
  计算机: ["计算机", "信息技术"],
  信息: ["信息技术", "计算机"],
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

function normalizeSearchText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[，。；、,.!！?？:：()（）[\]【】"'“”‘’_\-/\\]/g, "")
    .replace(/\s+/g, "");
}

function isSubsequence(needle, haystack) {
  let index = 0;
  for (const character of haystack) {
    if (character === needle[index]) index += 1;
    if (index === needle.length) return true;
  }
  return false;
}

function editDistanceWithin(left, right, limit) {
  if (Math.abs(left.length - right.length) > limit) return false;
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    const current = [row];
    let rowMinimum = current[0];
    for (let column = 1; column <= right.length; column += 1) {
      const cost = left[row - 1] === right[column - 1] ? 0 : 1;
      current[column] = Math.min(
        previous[column] + 1,
        current[column - 1] + 1,
        previous[column - 1] + cost,
      );
      rowMinimum = Math.min(rowMinimum, current[column]);
    }
    if (rowMinimum > limit) return false;
    previous = current;
  }
  return previous[right.length] <= limit;
}

function hasNearMatch(token, haystack) {
  if (token.length < 3) return false;
  const limit = token.length >= 6 ? 2 : 1;
  const minimumLength = Math.max(1, token.length - limit);
  const maximumLength = token.length + limit;
  for (let size = minimumLength; size <= maximumLength; size += 1) {
    for (let index = 0; index + size <= haystack.length; index += 1) {
      if (editDistanceWithin(token, haystack.slice(index, index + size), limit)) {
        return true;
      }
    }
  }
  return false;
}

function fuzzyTokenMatches(rawToken, haystack, searchFields) {
  const token = normalizeSearchText(rawToken);
  if (!token) return true;
  const alternatives = SEARCH_ALIASES[token] || [token];
  return alternatives.some(value => {
    const candidate = normalizeSearchText(value);
    return haystack.includes(candidate) ||
      (candidate.length >= 3 && isSubsequence(candidate, haystack)) ||
      (candidate.length === 2 && searchFields.some(field =>
        field.length >= 2 && field.length <= 4 &&
        editDistanceWithin(candidate, field, 1)
      )) ||
      hasNearMatch(candidate, haystack);
  });
}

function enableDesktopHorizontalScroll(container) {
  container.addEventListener("wheel", event => {
    if (container.scrollWidth <= container.clientWidth) return;
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    event.preventDefault();
    container.scrollLeft += event.deltaY;
  }, { passive: false });
}

function attachVisibleScrollControl(container, label) {
  const control = document.createElement("div");
  control.className = "custom-scroll-control";

  const left = document.createElement("button");
  left.type = "button";
  left.className = "scroll-arrow";
  left.textContent = "‹";
  left.setAttribute("aria-label", `${label}向左滚动`);

  const range = document.createElement("input");
  range.type = "range";
  range.className = "scroll-range";
  range.min = "0";
  range.max = "1000";
  range.value = "0";
  range.setAttribute("aria-label", `${label}横向滚动条`);

  const right = document.createElement("button");
  right.type = "button";
  right.className = "scroll-arrow";
  right.textContent = "›";
  right.setAttribute("aria-label", `${label}向右滚动`);

  control.append(left, range, right);
  container.insertAdjacentElement("afterend", control);

  function update() {
    const maxScroll = Math.max(0, container.scrollWidth - container.clientWidth);
    control.classList.toggle("has-overflow", maxScroll > 2);
    range.value = maxScroll ? String(Math.round(container.scrollLeft / maxScroll * 1000)) : "0";
    left.disabled = container.scrollLeft <= 1;
    right.disabled = container.scrollLeft >= maxScroll - 1;
  }

  range.addEventListener("input", () => {
    const maxScroll = Math.max(0, container.scrollWidth - container.clientWidth);
    container.scrollLeft = Number(range.value) / 1000 * maxScroll;
  });
  left.addEventListener("click", () => {
    container.scrollBy({ left: -container.clientWidth * 0.75, behavior: "smooth" });
  });
  right.addEventListener("click", () => {
    container.scrollBy({ left: container.clientWidth * 0.75, behavior: "smooth" });
  });
  container.addEventListener("scroll", update, { passive: true });
  new ResizeObserver(update).observe(container);
  new MutationObserver(update).observe(container, { childList: true });
  requestAnimationFrame(update);
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

function matchesTime(job) {
  if (state.months === "all") return true;
  if (!job.date || !/^\d{4}-\d{2}-\d{2}$/.test(job.date)) return false;

  const published = new Date(`${job.date}T00:00:00+08:00`);
  if (Number.isNaN(published.getTime())) return false;

  const cutoff = new Date();
  cutoff.setHours(0, 0, 0, 0);
  cutoff.setMonth(cutoff.getMonth() - Number(state.months));
  return published >= cutoff;
}

function matchesSource(job) {
  return state.sourceType === "all" || job.source_type === state.sourceType;
}

function passesExclusions(job) {
  return !(job.employment_terms || []).some(term => state.exclusions.has(term));
}

function matchesQuery(job) {
  const query = state.query.trim();
  if (!query) return true;
  const searchableValues = [
    job.title,
    job.source,
    ...(job.regions || []),
    ...(job.school_levels || []),
    ...(job.subjects || []),
    ...(job.matched_terms || []),
    ...(job.employment_terms || []),
  ];
  const searchFields = searchableValues.map(normalizeSearchText).filter(Boolean);
  const haystack = normalizeSearchText(searchableValues.join(" "));
  const tokens = query.split(/\s+/).filter(Boolean);
  return tokens.every(token => fuzzyTokenMatches(token, haystack, searchFields));
}

function render() {
  const jobs = state.jobs.filter(job =>
    matchesFilter(job) &&
    matchesQuery(job) &&
    matchesRegion(job) &&
    matchesLevel(job) &&
    matchesTime(job) &&
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
    [...new Set([
      ...(job.subjects || []),
      ...(job.employment_terms || []),
      ...(job.matched_terms || []),
    ])]
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

let searchTimer;
elements.search.addEventListener("input", event => {
  state.query = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(render, 100);
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
elements.timeChips.addEventListener("click", event => {
  const button = event.target.closest("[data-months]");
  if (!button) return;
  state.months = button.dataset.months;
  elements.timeChips.querySelectorAll(".time-chip").forEach(chip => {
    chip.classList.toggle("active", chip === button);
  });
  const labels = {
    all: "全部时间",
    1: "一个月内",
    3: "三个月内",
    6: "半年内",
    12: "一年内",
  };
  elements.selectedTimeText.textContent = labels[state.months];
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
[
  elements.regionChips,
  elements.levelChips,
  elements.timeChips,
  elements.chips,
].forEach(enableDesktopHorizontalScroll);
[
  [elements.regionChips, "地区选项"],
  [elements.levelChips, "学段选项"],
  [elements.timeChips, "时间选项"],
  [elements.chips, "公告类型选项"],
].forEach(([container, label]) => attachVisibleScrollControl(container, label));
loadJobs();
