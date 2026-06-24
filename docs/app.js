const DATA_URL = "./data/latest_jobs.json";
const FAVORITES_KEY = "baoding-teacher-favorites";

const state = {
  jobs: [],
  filter: "all",
  query: "",
  favorites: new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]")),
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
  dialog: document.querySelector("#helpDialog"),
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

function matchesFilter(job) {
  if (state.filter === "all") return true;
  if (state.filter === "favorite") return state.favorites.has(job.url);
  if (state.filter === "review") {
    return ["uncertain", "needs_review"].includes(job.classification);
  }
  return job.classification === state.filter;
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
  const jobs = state.jobs.filter(job => matchesFilter(job) && matchesQuery(job));
  elements.list.replaceChildren();
  elements.resultCount.textContent = `${jobs.length} 条`;
  elements.empty.classList.toggle("hidden", jobs.length !== 0);

  jobs.forEach((job, index) => {
    const fragment = elements.template.content.cloneNode(true);
    const card = fragment.querySelector(".job-card");
    const link = fragment.querySelector(".job-link");
    const badge = fragment.querySelector(".badge");
    const favorite = fragment.querySelector(".favorite-button");
    const [label, badgeClass] = labels[job.classification] || labels.needs_review;

    card.style.animationDelay = `${Math.min(index * 45, 250)}ms`;
    badge.textContent = label;
    if (badgeClass) badge.classList.add(badgeClass);
    link.href = job.url;
    fragment.querySelector(".job-title").textContent = job.title;
    fragment.querySelector(".job-date").textContent = job.date || "日期未识别";
    fragment.querySelector(".job-source").textContent = job.source;

    const terms = fragment.querySelector(".terms");
    (job.matched_terms || []).slice(0, 5).forEach(term => {
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
    elements.updateText.textContent = formatTime(data.generated_at);
    updateSummary();
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
document.querySelector("#installHelp").addEventListener("click", () => elements.dialog.showModal());
document.querySelector("#closeDialog").addEventListener("click", () => elements.dialog.close());
elements.dialog.addEventListener("click", event => {
  if (event.target === elements.dialog) elements.dialog.close();
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
}

loadJobs();
