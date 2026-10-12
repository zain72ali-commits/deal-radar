"use strict";

// Deal Radar dashboard. Reads data/deals.json written by the daily bot run.
// All deal text is inserted with textContent (never innerHTML), and links and
// images are only used when they point at OzBargain's own domains.

const DATA_URL = "data/deals.json";
const DEAL_URL_PREFIX = "https://www.ozbargain.com.au/node/";
const IMAGE_URL_PREFIX = "https://files.ozbargain.com.au/";
const STORAGE_KEY = "deal-radar-filters-v1";
const DAY_MS = 24 * 60 * 60 * 1000;

const VERDICT_LABELS = {
  strong: "Strong votes",
  positive: "Positive votes",
  mixed: "Mixed votes",
  early: "Early",
};
const UNIT_LABELS = { month: "/month", night: "/night", year: "/year", week: "/week" };
const DEFAULT_FILTERS = {
  category: "all",
  search: "",
  newOnly: false,
  pricedOnly: false,
  goodOnly: false,
  maxPrice: "",
  sort: "newest",
};

const aud = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" });
const shortDate = new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short" });
const longDate = new Intl.DateTimeFormat("en-AU", {
  weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
});

const el = (id) => document.getElementById(id);
const ui = {
  status: el("status"), alert: el("alert"), search: el("search"), categories: el("categories"),
  newOnly: el("new-only"), pricedOnly: el("priced-only"), goodOnly: el("good-only"),
  maxPrice: el("max-price"), sort: el("sort"), count: el("count"), deals: el("deals"), empty: el("empty"),
};

let deals = [];
let filters = loadFilters();

init();

async function init() {
  syncControls();
  bindControls();
  try {
    const data = await fetchData();
    deals = Array.isArray(data.deals) ? data.deals : [];
    renderHeader(data);
    renderCategories(Array.isArray(data.categories) ? data.categories : []);
    render();
  } catch (error) {
    ui.status.textContent = "Couldn't load deals yet. The first daily run may not have finished.";
    console.error(error);
  }
}

async function fetchData() {
  const response = await fetch(DATA_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status} loading ${DATA_URL}`);
  return response.json();
}

// ---------- filters ----------

function loadFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return { ...DEFAULT_FILTERS, ...saved };
  } catch {
    return { ...DEFAULT_FILTERS };
  }
}

function saveFilters() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  } catch {
    // Storage can be unavailable (private mode); filters just won't persist.
  }
}

function syncControls() {
  ui.search.value = filters.search;
  ui.newOnly.checked = filters.newOnly;
  ui.pricedOnly.checked = filters.pricedOnly;
  ui.goodOnly.checked = filters.goodOnly;
  ui.maxPrice.value = filters.maxPrice;
  ui.sort.value = filters.sort;
}

function bindControls() {
  const update = (key, value) => {
    filters = { ...filters, [key]: value };
    saveFilters();
    render();
  };
  ui.search.addEventListener("input", () => update("search", ui.search.value));
  ui.newOnly.addEventListener("change", () => update("newOnly", ui.newOnly.checked));
  ui.pricedOnly.addEventListener("change", () => update("pricedOnly", ui.pricedOnly.checked));
  ui.goodOnly.addEventListener("change", () => update("goodOnly", ui.goodOnly.checked));
  ui.maxPrice.addEventListener("input", () => update("maxPrice", ui.maxPrice.value));
  ui.sort.addEventListener("change", () => update("sort", ui.sort.value));
  ui.categories.addEventListener("click", (event) => {
    const chip = event.target.closest("button[data-slug]");
    if (!chip) return;
    update("category", chip.dataset.slug);
    for (const button of ui.categories.querySelectorAll("button")) {
      button.setAttribute("aria-pressed", String(button === chip));
    }
  });
}

function matches(deal) {
  // The data is a morning snapshot; hide deals that have ended since it was taken.
  if (deal.expires_at && Date.parse(deal.expires_at) <= Date.now()) return false;
  if (filters.category !== "all" && deal.category_slug !== filters.category) return false;
  if (filters.newOnly && !deal.is_new) return false;
  if (filters.pricedOnly && deal.price.amount === null) return false;
  if (filters.goodOnly && !["strong", "positive"].includes(deal.verdict)) return false;

  const maxPrice = Number.parseFloat(filters.maxPrice);
  if (!Number.isNaN(maxPrice) && deal.price.amount !== null && deal.price.amount > maxPrice) return false;

  const terms = filters.search.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length) {
    const haystack = [deal.title, deal.category, ...deal.tags].join(" ").toLowerCase();
    if (!terms.every((term) => haystack.includes(term))) return false;
  }
  return true;
}

const nullsLast = (a, b, compare) => (a === null ? (b === null ? 0 : 1) : b === null ? -1 : compare(a, b));
const SORTERS = {
  newest: (a, b) => Date.parse(b.posted_at) - Date.parse(a.posted_at),
  votes: (a, b) => (b.votes_pos - b.votes_neg) - (a.votes_pos - a.votes_neg),
  discount: (a, b) => nullsLast(a.price.discount_pct, b.price.discount_pct, (x, y) => y - x),
  price: (a, b) => nullsLast(a.price.amount, b.price.amount, (x, y) => x - y),
  ending: (a, b) => nullsLast(a.expires_at, b.expires_at, (x, y) => Date.parse(x) - Date.parse(y)),
};

// ---------- rendering ----------

function renderHeader(data) {
  const newCount = deals.filter((d) => d.is_new).length;
  const updated = data.generated_at ? longDate.format(new Date(data.generated_at)) : "unknown";
  ui.status.textContent = `Updated ${updated} · ${deals.length} live deals · ${newCount} new`;

  const failed = Array.isArray(data.failed_categories) ? data.failed_categories : [];
  ui.alert.hidden = failed.length === 0;
  ui.alert.textContent = failed.length
    ? `Couldn't check ${failed.join(", ")} on the last run, so their deals may be out of date.`
    : "";
}

function renderCategories(categories) {
  const counts = new Map();
  for (const deal of deals) counts.set(deal.category_slug, (counts.get(deal.category_slug) || 0) + 1);

  const options = [{ slug: "all", name: "All", count: deals.length }]
    .concat(categories.map((c) => ({ slug: c.slug, name: c.name, count: counts.get(c.slug) || 0 })));
  if (!options.some((o) => o.slug === filters.category)) filters = { ...filters, category: "all" };

  ui.categories.replaceChildren(...options.map((option) => {
    const button = node("button", { className: "chip", type: "button" }, option.name);
    button.dataset.slug = option.slug;
    button.setAttribute("aria-pressed", String(option.slug === filters.category));
    button.append(node("span", { className: "n" }, String(option.count)));
    return button;
  }));
}

function render() {
  const visible = deals.filter(matches).sort(SORTERS[filters.sort] || SORTERS.newest);
  ui.deals.replaceChildren(...visible.map(card));
  ui.empty.hidden = visible.length > 0 || deals.length === 0;
  ui.count.textContent = deals.length ? `Showing ${visible.length} of ${deals.length}` : "";
}

function card(deal) {
  const article = node("article", { className: deal.is_new ? "card is-new" : "card" });
  article.append(thumbnail(deal), node("div", { className: "body" },
    badges(deal),
    title(deal),
    priceLine(deal.price),
    metaLine(deal),
  ));
  return article;
}

function thumbnail(deal) {
  const blank = () => node("span", { className: "thumb blank" });
  if (typeof deal.image !== "string" || !deal.image.startsWith(IMAGE_URL_PREFIX)) return blank();
  const image = node("img", { className: "thumb", src: deal.image, alt: "", loading: "lazy", decoding: "async" });
  image.addEventListener("error", () => image.replaceWith(blank()), { once: true });
  return image;
}

function badges(deal) {
  const list = node("div", { className: "badges" });
  const add = (text, kind) => list.append(node("span", { className: `badge ${kind}` }, text));

  if (deal.is_new) add("New today", "new");
  add(VERDICT_LABELS[deal.verdict] || "Votes", deal.verdict);
  if (deal.history?.status === "new_low") add("Lowest price seen", "low");
  if (deal.history?.status === "matches_low") add("Matches lowest seen", "low");
  if (deal.history?.status === "above_low") {
    const when = shortDate.format(new Date(deal.history.previous_low_date));
    add(`Was ${aud.format(deal.history.previous_low)} on ${when}`, "mixed");
  }
  if (deal.long_running) add("Long running", "");
  if (!deal.confirmed_today) add(`Last confirmed ${shortDate.format(new Date(deal.last_confirmed))}`, "stale");
  return list;
}

function title(deal) {
  const heading = node("h2", { className: "title" });
  if (typeof deal.url === "string" && deal.url.startsWith(DEAL_URL_PREFIX)) {
    heading.append(node("a", { href: deal.url, target: "_blank", rel: "noopener noreferrer" }, deal.title));
  } else {
    heading.textContent = deal.title;
  }
  return heading;
}

function priceLine(price) {
  const line = node("div", { className: "price" });
  if (price.is_free) {
    line.append(node("span", { className: "now" }, "Free"));
  } else if (price.amount !== null) {
    line.append(node("span", { className: "now" }, aud.format(price.amount)));
    if (price.unit) line.append(node("span", { className: "unit" }, UNIT_LABELS[price.unit] || `/${price.unit}`));
  } else {
    line.append(node("span", { className: "none" }, "Price not in title"));
  }
  if (price.was) line.append(node("span", { className: "was" }, aud.format(price.was)));
  if (price.discount_pct) line.append(node("span", { className: "off" }, `−${price.discount_pct}%`));
  return line;
}

function metaLine(deal) {
  const meta = node("div", { className: "meta" },
    node("span", {}, deal.category),
    node("span", { className: "up" }, `▲ ${deal.votes_pos}`),
    node("span", { className: "down" }, `▼ ${deal.votes_neg}`),
    node("span", {}, `${deal.comments} comments`),
  );
  const ending = endingText(deal.expires_at);
  if (ending) meta.append(node("span", { className: ending.soon ? "ends-soon" : "" }, ending.text));
  return meta;
}

function endingText(expiresAt) {
  if (!expiresAt) return null;
  const expires = new Date(expiresAt);
  const days = Math.ceil((expires - Date.now()) / DAY_MS);
  const date = shortDate.format(expires);
  if (days <= 1) return { text: `Ends ${date} (within a day)`, soon: true };
  return { text: `Ends ${date} (${days} days)`, soon: days <= 3 };
}

function node(tag, props = {}, ...children) {
  const element = Object.assign(document.createElement(tag), props);
  for (const child of children) element.append(typeof child === "string" ? document.createTextNode(child) : child);
  return element;
}
