/* NetDeck front-end — dependency-free single-page app.
 * All tool output is inserted as text nodes (never innerHTML) to stay XSS-safe. */
"use strict";

(() => {
  // ───────────────────────────────── icons ─────────────────────────────────
  const P = {
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    radar: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><path d="M12 12 19 5"/>',
    gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    layers: '<path d="m12 2-10 5 10 5 10-5-10-5z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    network: '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/>',
    plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    home: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    sliders: '<path d="M4 21v-7"/><path d="M4 10V3"/><path d="M12 21v-9"/><path d="M12 8V3"/><path d="M20 21v-5"/><path d="M20 12V3"/><path d="M1 14h6"/><path d="M9 8h6"/><path d="M17 16h6"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    play: '<path d="M7 4.5v15a1 1 0 0 0 1.5.86l12-7.5a1 1 0 0 0 0-1.72l-12-7.5A1 1 0 0 0 7 4.5z"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    terminal: '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
    window: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M7 6.5h.01"/><path d="M10 6.5h.01"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    alert: '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    wifi: '<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><path d="M12 20h.01"/>',
    ethernet: '<path d="M6 10V6h12v4"/><rect x="3" y="10" width="18" height="10" rx="2"/><path d="M8 14v2"/><path d="M12 14v2"/><path d="M16 14v2"/>',
    vpn: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    loop: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    moon: '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    chevron: '<path d="m9 18 6-6-6-6"/>',
    arrowDown: '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
    arrowUp: '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>',
    key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    wrap: '<path d="M3 6h18"/><path d="M3 12h15a3 3 0 1 1 0 6h-4"/><path d="m16 16-2 2 2 2"/><path d="M3 18h7"/>',
    scroll: '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/><path d="M5 21h14"/>',
    menu: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
    pulse: '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
    server: '<rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><path d="M6 6h.01"/><path d="M6 18h.01"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    route: '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
  };
  const icon = (name, cls = "") =>
    `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || P.info}</svg>`;

  const TOOL_ICONS = {
    ping: "activity", "tcp-check": "plug", traceroute: "route", tracepath: "route", "mtr-report": "route",
    speedtest: "zap", "wifi-scan": "wifi", "wifi-link": "wifi", "tls-inspect": "lock", "public-ip": "globe",
    "http-headers": "globe", "http-timing": "clock", "iperf-server": "server", "route-get": "route",
    "listening": "server", "nmap-sweep": "radar", "arp-scan": "radar", "neighbors": "network", ethtool: "ethernet",
  };

  // ───────────────────────────────── helpers ───────────────────────────────
  const $ = (sel, root = document) => root.querySelector(sel);
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === "class") el.className = v;
        else if (k === "html") el.innerHTML = v; // only ever used with constant icon markup
        else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
        else if (k === "dataset") Object.assign(el.dataset, v);
        else el.setAttribute(k, v === true ? "" : v);
      }
    }
    for (const c of children.flat()) {
      if (c == null || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  const ic = (name, cls) => h("span", { html: icon(name, cls), class: "ic-wrap" }).firstChild;

  const store = {
    get(key, fallback) { try { const v = localStorage.getItem("netdeck." + key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem("netdeck." + key, JSON.stringify(value)); } catch { /* storage blocked */ } },
  };

  async function api(path, { method = "GET", body } = {}) {
    const opt = { method, headers: {}, credentials: "same-origin" };
    if (method !== "GET") {
      opt.headers["X-NetDeck"] = "1";
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body || {});
    }
    const res = await fetch(path, opt);
    let data = {};
    try { data = await res.json(); } catch { /* empty body */ }
    if (!res.ok) {
      const err = new Error(data.error || (data.errors ? "Please fix the highlighted fields." : res.statusText));
      err.status = res.status; err.data = data;
      if (res.status === 401) location.reload();
      throw err;
    }
    return data;
  }

  function fmtRate(bps) {
    const bits = bps * 8;
    if (bits < 1000) return `${bits.toFixed(0)} bit/s`;
    if (bits < 1e6) return `${(bits / 1e3).toFixed(1)} kbit/s`;
    if (bits < 1e9) return `${(bits / 1e6).toFixed(1)} Mbit/s`;
    return `${(bits / 1e9).toFixed(2)} Gbit/s`;
  }
  function fmtBytes(b) {
    const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
    while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return `${b.toFixed(i ? 1 : 0)} ${u[i]}`;
  }
  function fmtDur(sec) {
    sec = Math.max(0, Math.round(sec));
    const m = Math.floor(sec / 60), s = sec % 60;
    return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  function fmtTime(ts) {
    const d = new Date(ts * 1000);
    const today = new Date().toDateString() === d.toDateString();
    return today ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  async function copyText(text, what = "Copied to clipboard") {
    try { await navigator.clipboard.writeText(text); toast("ok", what); }
    catch { toast("fail", "Clipboard unavailable", "Select the text and copy it manually."); }
  }

  function toast(kind, title, detail) {
    const name = { ok: "check", fail: "alert", info: "info" }[kind] || "info";
    const el = h("div", { class: `toast ${kind}`, role: "status" }, ic(name), h("div", null, h("b", null, title), detail ? h("span", null, detail) : null));
    $("#toasts").append(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 250); }, kind === "fail" ? 6500 : 3500);
  }

  // ───────────────────────────────── state ─────────────────────────────────
  const S = {
    meta: null, categories: [], tools: [], byId: {}, system: null,
    lastJob: store.get("lastJob", {}), // toolId -> jobId
    jobs: [], cleanup: [], history: {}, // iface -> [{rx,tx}]
  };
  const STATUS = {
    running: ["run", "Running"], done: ["ok", "Completed"], failed: ["fail", "Failed"],
    stopped: ["warn", "Stopped"], error: ["fail", "Error"],
  };
  const MODE = {
    stream: { label: "Run", icon: "play", badge: null },
    terminal: { label: "Open in terminal", icon: "terminal", badge: ["terminal", "Terminal"] },
    gui: { label: "Launch app", icon: "window", badge: ["window", "Desktop app"] },
  };
  const toolIcon = (t) => (t.mode === "terminal" ? "terminal" : t.mode === "gui" ? "window" : TOOL_ICONS[t.id] || catOf(t).icon);
  const catOf = (t) => S.categories.find((c) => c.id === t.category) || { name: "", icon: "info" };

  function onCleanup(fn) { S.cleanup.push(fn); }
  function runCleanup() { while (S.cleanup.length) { try { S.cleanup.pop()(); } catch (e) { console.error(e); } } }

  // ───────────────────────────────── theme ─────────────────────────────────
  const ACCENTS = [
    ["#7c8cff", "Indigo"], ["#4f9dff", "Blue"], ["#2dd4bf", "Teal"], ["#3ecf8e", "Green"],
    ["#f5a524", "Amber"], ["#e0a19b", "Rose gold"], ["#f472b6", "Pink"], ["#a78bfa", "Violet"],
  ];
  function applyTheme() {
    const pref = store.get("theme", "system");
    const dark = pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    $("#theme-btn").innerHTML = icon(dark ? "sun" : "moon");
    const accent = store.get("accent", null);
    if (accent) document.documentElement.style.setProperty("--accent", accent);
    else document.documentElement.style.removeProperty("--accent");
    document.documentElement.style.setProperty("--console-size", `${store.get("consoleSize", 12.5)}px`);
  }
  // ───────────────────────────────── shell ─────────────────────────────────
  function renderNav(route) {
    const nav = $("#nav");
    const running = S.jobs.filter((j) => j.status === "running").length;
    const link = (href, iconName, label, extra, active) =>
      h("a", { href, class: active ? "active" : "", "aria-current": active ? "page" : null }, ic(iconName), h("span", null, label), extra);
    const counts = {};
    S.tools.forEach((t) => { counts[t.category] = (counts[t.category] || 0) + 1; });
    const activeCat = route.name === "category" ? route.id : route.name === "tool" ? (S.byId[route.id] || {}).category : null;
    nav.replaceChildren(
      link("#/", "home", "Overview", null, route.name === "overview"),
      link("#/activity", "clock", "Activity", running ? h("span", { class: "live" }, running) : null, route.name === "activity"),
      h("div", { class: "nav-label" }, "Toolbox"),
      ...S.categories.map((c) => link(`#/c/${c.id}`, c.icon, c.name, h("span", { class: "count" }, counts[c.id] || 0), activeCat === c.id)),
      h("div", { class: "nav-label" }, "App"),
      link("#/settings", "sliders", "Settings", null, route.name === "settings"),
    );
  }

  function renderCrumbs(parts) {
    const el = $("#crumbs");
    const nodes = [];
    parts.forEach((p, i) => {
      if (i) nodes.push(ic("chevron", "sm"));
      nodes.push(p.href ? h("a", { href: p.href }, p.label) : h("span", { class: "here" }, p.label));
    });
    el.replaceChildren(...nodes);
  }

  function renderTopStatus() {
    const pm = S.meta.privilege;
    const cls = pm.available ? "ok" : "warn";
    const label = { root: "Root", sudo: "sudo ready", pkexec: "polkit", none: "No admin" }[pm.mode] || pm.mode;
    $("#top-status").replaceChildren(h("span", { class: `badge ${cls}`, title: pm.description }, ic("key"), label));
    $("#sidebar-foot").replaceChildren(
      h("div", { class: "host" }, h("span", { class: "dot ok" }), S.meta.hostname),
      h("div", null, `${S.meta.user} · NetDeck ${S.meta.version}`),
    );
  }

  // ───────────────────────────────── router ────────────────────────────────
  function parseRoute() {
    const hash = location.hash.replace(/^#\/?/, "");
    const [path, query] = hash.split("?");
    const params = new URLSearchParams(query || "");
    const seg = path.split("/").filter(Boolean);
    if (seg[0] === "c" && seg[1]) return { name: "category", id: seg[1] };
    if (seg[0] === "t" && seg[1]) return { name: "tool", id: seg[1], job: params.get("job") };
    if (seg[0] === "activity") return { name: "activity" };
    if (seg[0] === "settings") return { name: "settings" };
    return { name: "overview" };
  }

  function navigate() {
    runCleanup();
    const route = parseRoute();
    $("#app").classList.remove("nav-open");
    renderNav(route);
    const content = $("#content");
    content.scrollTop = 0;
    const view = { overview: viewOverview, category: viewCategory, tool: viewTool, activity: viewActivity, settings: viewSettings }[route.name];
    try {
      content.replaceChildren(view(route));
    } catch (err) {
      console.error(err);
      content.replaceChildren(h("div", { class: "page" }, h("div", { class: "callout fail" }, ic("alert"),
        h("div", null, h("b", null, "This page failed to render. "), String(err && err.stack || err)))));
    }
  }

  // ───────────────────────────────── overview ──────────────────────────────
  const HC_STEPS = [
    ["link", "Network link", "ethernet"], ["gateway", "Gateway", "route"], ["dns", "DNS", "globe"],
    ["internet", "Internet", "link"], ["https", "HTTPS", "lock"],
  ];

  function viewOverview() {
    renderCrumbs([{ label: "Overview" }]);
    const page = h("div", { class: "page" });
    const sys = S.system;
    const hcCard = h("section", { class: "card" });
    const netCard = h("section", { class: "card" });
    const ifaceGrid = h("div", { class: "grid ifaces" });
    const quick = h("div", { class: "grid tools" });

    page.append(
      h("div", { class: "page-head" },
        h("div", { class: "grow" }, h("h1", null, "Network overview"),
          h("p", null, sys ? `${sys.hostname} · ${sys.os} · kernel ${sys.kernel}` : "Loading…")),
        h("button", { class: "btn", onclick: () => refreshSystem().then(navigate) }, ic("loop"), "Refresh")),
      h("div", { class: "grid ov-top" }, hcCard, netCard),
      h("div", { class: "section-title" }, h("h2", null, "Interfaces"), h("span", { class: "sub" }, "Live throughput, updated every second")),
      ifaceGrid,
      h("div", { class: "section-title" }, h("h2", null, "Popular tools"), h("span", { class: "sub" }, "One click to the most-used diagnostics")),
      quick,
    );

    // health check
    const chain = h("div", { class: "hc-chain" });
    const verdict = h("div", { class: "hc-verdict" }, ic("info"), "Checks each layer in order and pinpoints where connectivity breaks.");
    const runBtn = h("button", { class: "btn primary" }, ic("pulse"), "Run diagnosis");
    const drawSteps = (steps, running) => {
      chain.replaceChildren(...HC_STEPS.map(([id, label, iconName]) => {
        const s = steps && steps.find((x) => x.id === id);
        const status = running ? "run" : s ? s.status : "";
        const node = h("div", { class: "hc-node" }, ic(s && s.status === "fail" ? "x" : s && s.status === "ok" ? "check" : iconName));
        const detail = s ? [s.detail, s.ms != null ? h("span", { class: "hc-ms" }, ` · ${s.ms} ms`) : null] : running ? "Checking…" : "Not run yet";
        return h("div", { class: `hc-step ${status}` }, node, h("div", { class: "hc-text" }, h("div", { class: "hc-label" }, label), h("div", { class: "hc-detail" }, detail)));
      }));
    };
    const runHealth = async () => {
      runBtn.disabled = true; drawSteps(null, true);
      verdict.replaceChildren(h("div", { class: "spinner" }), "Diagnosing your connection…");
      try {
        const res = await api("/api/health", { method: "POST" });
        drawSteps(res.steps, false);
        S.lastHealth = res.steps;
        const firstBad = res.steps.find((s) => s.status === "fail");
        const warn = res.steps.find((s) => s.status === "warn");
        verdict.replaceChildren(
          ic(firstBad ? "alert" : "check"),
          firstBad ? `Problem found at "${firstBad.label}": ${firstBad.detail}` :
            warn ? `Mostly healthy — check "${warn.label}": ${warn.detail}` : "All layers healthy — your connection is working end to end.",
        );
      } catch (e) { verdict.replaceChildren(ic("alert"), e.message); drawSteps(null, false); }
      runBtn.disabled = false;
    };
    runBtn.addEventListener("click", runHealth);
    drawSteps(S.lastHealth, false);
    hcCard.append(
      h("div", { class: "card-head" }, h("h2", null, "Connection health"), h("span", { class: "spacer" }), runBtn),
      h("div", { class: "card-body" }, chain, verdict),
    );

    // network details
    if (sys) {
      const pri = sys.primary || {};
      const dns = sys.dns.upstream.length ? sys.dns.upstream : sys.dns.servers;
      const chips = (arr) => (arr.length ? arr.map((x) => h("span", { class: "chip" }, x)) : "—");
      netCard.append(
        h("div", { class: "card-head" }, h("h2", null, "Network details")),
        h("div", { class: "card-body" },
          h("dl", { class: "kv" },
            h("dt", null, "Gateway"), h("dd", null, pri.gateway ? `${pri.gateway} via ${pri.iface}` : "—"),
            h("dt", null, "Local IP"), h("dd", null, pri.ip || "—"),
            h("dt", null, "Subnet"), h("dd", null, pri.subnet || "—"),
            h("dt", null, "DNS"), h("dd", null, chips(dns)),
            sys.dns.resolved_stub ? [h("dt", null, "Resolver"), h("dd", null, "systemd-resolved (127.0.0.53)")] : null,
            h("dt", null, "Search"), h("dd", null, chips(sys.dns.search)),
            h("dt", null, "Routes"), h("dd", null, `${sys.routes.length} (${sys.routes.filter((r) => r.family === "inet").length} IPv4)`)),
          h("div", { class: "quick-row" },
            pri.gateway ? quickLink("Ping gateway", "activity", "ping", { host: pri.gateway, count: 10 }) : null,
            pri.subnet ? quickLink("Scan my network", "radar", "nmap-sweep", { target: pri.subnet }) : null,
            quickLink("Speed test", "zap", "speedtest", {}),
            quickLink("Public IP", "globe", "public-ip", {}))),
      );
      // interfaces
      const ifaces = sys.interfaces.filter((i) => !i.loopback).sort((a, b) => (a.state === "up" ? -1 : 1) - (b.state === "up" ? -1 : 1));
      if (!ifaces.length) ifaceGrid.append(h("div", { class: "card empty" }, ic("network"), h("b", null, "No network interfaces")));
      const live = {};
      ifaces.forEach((i) => { const card = ifaceCard(i); live[i.name] = card; ifaceGrid.append(card.el); });
      startStats(live);
    }

    // popular
    S.tools.filter((t) => t.popular).slice(0, 12).forEach((t) => quick.append(toolCard(t, true)));
    return page;
  }

  function quickLink(label, iconName, toolId, prefill) {
    const t = S.byId[toolId];
    if (!t) return null;
    return h("button", { class: "btn sm", onclick: () => { store.set(`params.${toolId}`, { ...(store.get(`params.${toolId}`, {})), ...prefill }); location.hash = `#/t/${toolId}`; } }, ic(iconName, "sm"), label);
  }

  function signalBars(dbm) {
    const level = dbm >= -55 ? 4 : dbm >= -65 ? 3 : dbm >= -75 ? 2 : dbm >= -85 ? 1 : 0;
    const el = h("span", { class: "signal", title: `${dbm} dBm` });
    [4, 7, 10, 13].forEach((ht, i) => { const b = h("i", { class: i < level ? "on" : "" }); b.style.height = `${ht}px`; el.append(b); });
    return el;
  }

  function ifaceCard(i) {
    const up = i.state === "up";
    const kindIcon = { wifi: "wifi", ethernet: "ethernet", vpn: "vpn", bridge: "network", virtual: "layers" }[i.kind] || "network";
    const kindLabel = { wifi: "Wi-Fi", ethernet: "Ethernet", vpn: "VPN / tunnel", bridge: "Bridge", virtual: "Virtual" }[i.kind] || i.kind;
    const rx = h("span"), tx = h("span"), rxTot = h("small"), txTot = h("small");
    const canvas = h("canvas", { class: "spark", "aria-hidden": "true" });
    const v4 = i.addresses.filter((a) => a.family === "inet");
    const v6 = i.addresses.filter((a) => a.family === "inet6" && a.scope === "global");
    const meta = [];
    if (i.wifi && i.wifi.ssid) meta.push(h("span", null, i.wifi.signal_dbm != null ? signalBars(i.wifi.signal_dbm) : null, " ", h("b", null, i.wifi.ssid)));
    if (i.wifi && i.wifi.freq_mhz) meta.push(h("span", null, h("b", null, (i.wifi.freq_mhz / 1000).toFixed(1)), " GHz"));
    if (i.wifi && i.wifi.tx_bitrate) meta.push(h("span", null, h("b", null, i.wifi.tx_bitrate)));
    if (i.speed_mbps) meta.push(h("span", null, h("b", null, i.speed_mbps >= 1000 ? `${i.speed_mbps / 1000} Gbit/s` : `${i.speed_mbps} Mbit/s`), " link"));
    if (i.mac) meta.push(h("span", null, "MAC ", h("b", null, i.mac)));
    if (i.mtu) meta.push(h("span", null, "MTU ", h("b", null, i.mtu)));
    const el = h("article", { class: `card iface ${up ? "" : "down"}` },
      h("div", { class: "iface-head" },
        h("div", { class: "iface-icon" }, ic(kindIcon)),
        h("div", null, h("div", { class: "iface-name" }, i.name), h("div", { class: "iface-kind" }, kindLabel)),
        h("span", { class: `badge ${up ? "ok" : "muted"}` }, h("span", { class: `dot ${up ? "ok" : ""}` }), up ? "Up" : i.state)),
      v4.length || v6.length ? h("div", { class: "iface-addrs" },
        v4.map((a) => h("div", null, h("span", { class: "fam" }, "IPv4"), `${a.address}/${a.prefix}`)),
        v6.slice(0, 2).map((a) => h("div", null, h("span", { class: "fam" }, "IPv6"), `${a.address}/${a.prefix}`))) :
        h("div", { class: "iface-addrs" }, h("div", null, "No IP address")),
      h("div", { class: "rates" },
        h("div", { class: "rate rx" }, ic("arrowDown"), rx, rxTot),
        h("div", { class: "rate tx" }, ic("arrowUp"), tx, txTot)),
      canvas,
      meta.length ? h("div", { class: "iface-meta" }, meta) : null,
    );
    return {
      el,
      update(r) {
        rx.textContent = fmtRate(r.rx); tx.textContent = fmtRate(r.tx);
        rxTot.textContent = fmtBytes(r.rx_total); txTot.textContent = fmtBytes(r.tx_total);
        const hist = (S.history[i.name] = S.history[i.name] || Array.from({ length: 90 }, () => ({ rx: 0, tx: 0 })));
        hist.push({ rx: r.rx, tx: r.tx });
        if (hist.length > 90) hist.shift();
        drawSpark(canvas, hist);
      },
    };
  }

  function drawSpark(canvas, hist) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, ht = canvas.clientHeight;
    if (!w) return;
    if (canvas.width !== w * dpr) { canvas.width = w * dpr; canvas.height = ht * dpr; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, ht);
    const max = Math.max(1024, ...hist.map((p) => Math.max(p.rx, p.tx))) * 1.15;
    const css = getComputedStyle(document.documentElement);
    const series = [["tx", css.getPropertyValue("--accent-2").trim()], ["rx", css.getPropertyValue("--accent").trim()]];
    const n = 90, step = w / (n - 1), off = n - hist.length;
    for (const [key, color] of series) {
      ctx.beginPath();
      hist.forEach((p, idx) => { const x = (off + idx) * step, y = ht - 2 - (p[key] / max) * (ht - 6); idx ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.lineJoin = "round"; ctx.stroke();
      if (hist.length > 1) {
        ctx.lineTo((off + hist.length - 1) * step, ht); ctx.lineTo(off * step, ht); ctx.closePath();
        const g = ctx.createLinearGradient(0, 0, 0, ht);
        g.addColorStop(0, color + "40"); g.addColorStop(1, color + "00");
        ctx.fillStyle = g; ctx.fill();
      }
    }
  }

  function startStats(live) {
    const es = new EventSource("/api/stats/stream");
    es.addEventListener("stats", (ev) => {
      const data = JSON.parse(ev.data);
      for (const [name, card] of Object.entries(live)) if (data.rates[name]) card.update(data.rates[name]);
    });
    onCleanup(() => es.close());
  }

  // ───────────────────────────────── category ──────────────────────────────
  function toolCard(t, showCat) {
    const badges = [];
    if (MODE[t.mode].badge) badges.push(h("span", { class: "badge" }, ic(MODE[t.mode].badge[0]), MODE[t.mode].badge[1]));
    if (t.privileged === true) badges.push(h("span", { class: "badge warn" }, ic("key"), "Admin"));
    if (t.long_running) badges.push(h("span", { class: "badge" }, ic("loop"), "Runs until stopped"));
    if (!t.installed) badges.push(h("span", { class: "badge fail" }, "Not installed"));
    if (showCat) badges.push(h("span", { class: "badge muted" }, catOf(t).name));
    return h("a", { class: `card tool-card ${t.installed ? "" : "missing"}`, href: `#/t/${t.id}` },
      h("span", { class: "go" }, ic("chevron")),
      h("div", { class: "tool-card-head" }, h("div", { class: "tool-icon" }, ic(toolIcon(t))),
        h("div", null, h("h3", null, t.name), h("div", { class: "bin" }, t.binary || "built-in"))),
      h("p", null, t.summary),
      badges.length ? h("div", { class: "badges" }, badges) : null);
  }

  function viewCategory(route) {
    const cat = S.categories.find((c) => c.id === route.id);
    if (!cat) { location.hash = "#/"; return h("div"); }
    renderCrumbs([{ label: "Toolbox" }, { label: cat.name }]);
    const tools = S.tools.filter((t) => t.category === cat.id).sort((a, b) => (b.installed - a.installed) || 0);
    const installed = tools.filter((t) => t.installed).length;
    return h("div", { class: "page" },
      h("div", { class: "page-head" },
        h("div", { class: "tool-icon lg-cat" }, ic(cat.icon, "lg")),
        h("div", { class: "grow" }, h("h1", null, cat.name), h("p", null, `${cat.summary} · ${installed} of ${tools.length} tools available`))),
      h("div", { class: "grid tools" }, tools.map((t) => toolCard(t))));
  }

  // ───────────────────────────────── tool ──────────────────────────────────
  function defaultFor(p) {
    if (p.prefill && S.system && S.system.primary) {
      const v = S.system.primary[p.prefill];
      if (v) return v;
    }
    return p.default;
  }

  function buildField(p, values, onChange) {
    const id = `f-${p.name}`;
    const field = h("div", { class: "field", dataset: { name: p.name } });
    const err = h("div", { class: "err" });
    const label = h("label", { for: id }, p.label, p.required ? h("span", { class: "req" }, "*") : null);
    const set = (v) => { values[p.name] = v; onChange(); };
    let control;
    const cur = values[p.name];

    if (p.kind === "bool") {
      const input = h("input", { type: "checkbox", id });
      input.checked = !!cur;
      input.addEventListener("change", () => set(input.checked));
      field.append(h("label", { class: "switch" }, input, h("span", { class: "track" }), h("span", null, p.label)));
      if (p.help) field.append(h("div", { class: "help" }, p.help));
      return field;
    }
    if (p.kind === "choice") {
      const short = p.choices.length <= 4 && p.choices.every(([, l]) => l.length <= 12);
      if (short) {
        control = h("div", { class: "seg", role: "radiogroup", "aria-label": p.label });
        p.choices.forEach(([v, l]) => {
          const b = h("button", { type: "button", role: "radio", class: String(cur) === v ? "on" : "", "aria-checked": String(String(cur) === v) }, l);
          b.addEventListener("click", () => {
            control.querySelectorAll("button").forEach((x) => { x.classList.remove("on"); x.setAttribute("aria-checked", "false"); });
            b.classList.add("on"); b.setAttribute("aria-checked", "true"); set(v);
          });
          control.append(b);
        });
        field.append(h("div", { class: "label" }, p.label), control);
      } else {
        control = h("select", { class: "input", id }, p.choices.map(([v, l]) => h("option", { value: v }, l)));
        control.value = cur ?? "";
        control.addEventListener("change", () => set(control.value));
        field.append(label, control);
      }
    } else if (p.kind === "iface") {
      const ifaces = (S.system ? S.system.interfaces : []).filter((i) => !i.loopback || p.allow_any);
      const opts = [];
      if (!p.required) opts.push(h("option", { value: "" }, p.allow_any ? "— none —" : "All interfaces"));
      if (p.allow_any) opts.push(h("option", { value: "any" }, "any (all interfaces)"));
      ifaces.forEach((i) => opts.push(h("option", { value: i.name }, `${i.name} — ${i.state}${i.addresses.find((a) => a.family === "inet") ? " · " + i.addresses.find((a) => a.family === "inet").address : ""}`)));
      control = h("select", { class: "input", id }, opts);
      control.value = cur ?? "";
      if (control.value !== (cur ?? "") && control.options.length) { control.selectedIndex = 0; values[p.name] = control.value; }
      control.addEventListener("change", () => set(control.value));
      field.append(label, control);
    } else {
      const numeric = p.kind === "int" || p.kind === "port";
      control = h("input", {
        class: "input", id, type: numeric ? "number" : "text", placeholder: p.placeholder || "",
        min: p.min ?? (p.kind === "port" ? 1 : null), max: p.max ?? (p.kind === "port" ? 65535 : null),
        autocomplete: "off", spellcheck: "false", list: ["host", "target", "hosts", "ip"].includes(p.kind) ? "dl-hosts" : null,
      });
      control.value = cur ?? "";
      control.addEventListener("input", () => set(control.value));
      field.append(label, control);
    }
    if (p.help) field.append(h("div", { class: "help" }, p.help));
    field.append(err);
    return field;
  }

  function hostSuggestions() {
    const dl = h("datalist", { id: "dl-hosts" });
    const seen = new Set();
    const add = (v) => { if (v && !seen.has(v)) { seen.add(v); dl.append(h("option", { value: v })); } };
    store.get("recentHosts", []).forEach(add);
    if (S.system && S.system.primary) { add(S.system.primary.gateway); add(S.system.primary.subnet); }
    ["1.1.1.1", "8.8.8.8", "example.com"].forEach(add);
    return dl;
  }
  function rememberHosts(tool, values) {
    const hosts = tool.params.filter((p) => ["host", "target", "ip"].includes(p.kind)).map((p) => values[p.name]).filter(Boolean);
    if (!hosts.length) return;
    const list = [...new Set([...hosts.map(String), ...store.get("recentHosts", [])])].slice(0, 15);
    store.set("recentHosts", list);
  }

  function viewTool(route) {
    const t = S.byId[route.id];
    if (!t) { location.hash = "#/"; return h("div"); }
    const cat = catOf(t);
    renderCrumbs([{ label: cat.name, href: `#/c/${cat.id}` }, { label: t.name }]);

    const saved = store.get(`params.${t.id}`, {});
    const values = {};
    t.params.forEach((p) => { values[p.name] = saved[p.name] !== undefined ? saved[p.name] : defaultFor(p); });

    // header
    const badges = [];
    if (MODE[t.mode].badge) badges.push(h("span", { class: "badge accent" }, ic(MODE[t.mode].badge[0]), MODE[t.mode].badge[1]));
    else badges.push(h("span", { class: "badge accent" }, ic("terminal"), "Live output"));
    if (t.privileged === true) badges.push(h("span", { class: "badge warn" }, ic("key"), "Needs admin"));
    if (t.privileged === "conditional") badges.push(h("span", { class: "badge muted", title: "Some options need administrator rights" }, ic("key"), "Admin for some options"));
    if (t.long_running) badges.push(h("span", { class: "badge" }, ic("loop"), "Runs until stopped"));
    badges.push(h("span", { class: `badge ${t.installed ? "ok" : "fail"}` }, t.installed ? ic("check") : ic("x"), t.binary ? (t.installed ? t.binary : `${t.binary} not installed`) : "Built-in"));

    const page = h("div", { class: "page" },
      h("div", { class: "tool-head" },
        h("div", { class: "tool-icon" }, ic(toolIcon(t))),
        h("div", { class: "grow" }, h("h1", null, t.name), h("p", null, t.summary), h("div", { class: "badges" }, badges))),
      hostSuggestions());

    // form
    const form = h("form", { class: "card form-card", novalidate: true });
    const previewCmds = h("div", { class: "cmds" });
    const preview = h("div", { class: "cmd-preview" }, previewCmds,
      h("button", { class: "copy", type: "button", title: "Copy command", "aria-label": "Copy command", onclick: () => copyText(previewCmds.innerText.trim(), "Command copied") }, ic("copy", "sm")));
    const runBtn = h("button", { class: "btn primary lg", type: "submit", disabled: !t.installed }, ic(MODE[t.mode].icon, t.mode === "stream" ? "fill" : ""), MODE[t.mode].label);
    const stopBtn = h("button", { class: "btn danger lg", type: "button", hidden: true }, ic("stop", "fill"), "Stop");

    let previewTimer = 0;
    let attempted = false;
    const touched = new Set();
    const fieldsEls = {};
    form.addEventListener("input", (e) => { const f = e.target.closest(".field"); if (f) touched.add(f.dataset.name); });
    form.addEventListener("click", (e) => { const f = e.target.closest(".field"); if (f) touched.add(f.dataset.name); });
    const onChange = () => {
      store.set(`params.${t.id}`, values);
      clearTimeout(previewTimer);
      previewTimer = setTimeout(updatePreview, 220);
    };
    async function updatePreview() {
      try {
        const res = await api("/api/preview", { method: "POST", body: { tool: t.id, params: values } });
        Object.values(fieldsEls).forEach((f) => f.classList.remove("invalid"));
        if (res.errors) {
          for (const [k, msg] of Object.entries(res.errors)) {
            if (fieldsEls[k] && (attempted || touched.has(k))) { fieldsEls[k].classList.add("invalid"); $(".err", fieldsEls[k]).textContent = msg; }
          }
          previewCmds.replaceChildren(h("div", { class: "cmd" }, "…complete the required fields"));
        } else {
          previewCmds.replaceChildren(...res.commands.map((c) => h("div", { class: "cmd" }, c)));
        }
      } catch (e) { previewCmds.replaceChildren(h("div", { class: "cmd" }, e.message)); }
    }

    if (!t.installed) {
      form.append(h("div", { class: "callout fail" }, ic("alert"), h("div", null,
        h("b", null, `${t.binary} is not installed. `),
        t.install_hint ? ["Install it with ", h("code", null, t.install_hint), " ", h("button", { class: "btn sm ghost", type: "button", onclick: () => copyText(t.install_hint) }, ic("copy", "sm"))] :
          "Install it with your distribution's package manager.")));
    }
    if (t.notes) form.append(h("div", { class: "callout" }, ic("info"), t.notes));
    if (t.privileged === true && !S.meta.privilege.available && t.mode === "stream") {
      form.append(h("div", { class: "callout warn" }, ic("key"), S.meta.privilege.description));
    }
    const basic = t.params.filter((p) => !p.advanced), adv = t.params.filter((p) => p.advanced);
    basic.forEach((p) => { const f = buildField(p, values, onChange); fieldsEls[p.name] = f; form.append(f); });
    if (adv.length) {
      const fields = h("div", { class: "fields" });
      adv.forEach((p) => { const f = buildField(p, values, onChange); fieldsEls[p.name] = f; fields.append(f); });
      form.append(h("details", { class: "adv", open: store.get(`adv.${t.id}`, false) || null,
        ontoggle: (e) => store.set(`adv.${t.id}`, e.target.open) },
      h("summary", null, ic("chevron", "sm"), `Advanced options (${adv.length})`), fields));
    }
    if (!t.params.length) form.append(h("div", { class: "help" }, "This tool has no options."));
    form.append(h("div", { class: "cmd-label" }, "Command"), preview, h("div", { class: "run-row" }, runBtn, stopBtn),
      h("div", { class: "hint" }, h("kbd", null, "Ctrl"), " + ", h("kbd", null, "Enter"), " to run"));

    // output side
    let consoleCtl = null;
    let right;
    if (t.mode === "stream") {
      consoleCtl = makeConsole(t, {
        onState(running) { stopBtn.hidden = !running; runBtn.lastChild.textContent = running ? "Run again" : "Run"; },
        stop: () => api(`/api/jobs/${consoleCtl.jobId}/stop`, { method: "POST" }).catch((e) => toast("fail", "Could not stop", e.message)),
      });
      right = consoleCtl.el;
      stopBtn.addEventListener("click", consoleCtl.stop);
      onCleanup(() => consoleCtl.detach());
    } else {
      const term = S.meta.terminal;
      right = h("div", { class: "card launch-panel" },
        h("div", { class: "big" }, ic(t.mode === "gui" ? "window" : "terminal")),
        h("h3", null, t.mode === "gui" ? "Opens as a desktop application" : `Opens in ${term || "your terminal"}`),
        h("p", null, t.mode === "gui" ? `${t.name} has its own graphical interface. NetDeck launches it for you.`
          : `${t.name} is interactive, so it runs in a real terminal window.` +
            (t.privileged === true || t.privileged === "conditional" ? " You'll be asked for your password there if needed." : "")),
        !term && t.mode === "terminal" ? h("div", { class: "callout warn" }, ic("alert"), "No terminal emulator detected — choose one in Settings.") : null);
    }
    page.append(h("div", { class: "workspace" }, form, right));

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!t.installed) return;
      attempted = true;
      runBtn.disabled = true;
      try {
        const res = await api("/api/run", { method: "POST", body: { tool: t.id, params: values } });
        rememberHosts(t, values);
        if (res.launched) {
          toast("ok", `${t.name} launched`, res.command);
        } else {
          S.lastJob[t.id] = res.job.id; store.set("lastJob", S.lastJob);
          history.replaceState(null, "", `#/t/${t.id}?job=${res.job.id}`);
          consoleCtl.attach(res.job.id);
          refreshJobs();
        }
      } catch (err) {
        if (err.data && err.data.errors) {
          for (const [k, msg] of Object.entries(err.data.errors)) if (fieldsEls[k]) { fieldsEls[k].classList.add("invalid"); $(".err", fieldsEls[k]).textContent = msg; }
        }
        toast("fail", `Couldn't start ${t.name}`, err.message);
      } finally { runBtn.disabled = !t.installed; }
    });
    const keyHandler = (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); form.requestSubmit(); } };
    document.addEventListener("keydown", keyHandler);
    onCleanup(() => document.removeEventListener("keydown", keyHandler));

    updatePreview();
    const jobId = route.job || S.lastJob[t.id];
    if (consoleCtl && jobId) consoleCtl.attach(jobId, true);
    return page;
  }

  // ───────────────────────────────── console ───────────────────────────────
  const HL = new RegExp([
    "(?<bad>\\b(?:error|errors|fail(?:ed|ure)?|unreachable|timed? ?out|timeout|refused|denied|closed|lost|no answer|NXDOMAIN|SERVFAIL|unknown host)\\b|✗)",
    "(?<ok>\\b(?:open|success(?:ful)?|connected|reachable|NOERROR|verified|up)\\b|✓)",
    "(?<warn>\\b(?:filtered|warning|retransmi\\w*|dup!?|expires? soon)\\b|⚠)",
    "(?<ip>\\b(?:\\d{1,3}\\.){3}\\d{1,3}(?:/\\d{1,2})?(?::\\d+)?\\b|\\b(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{1,4}\\b)",
    "(?<num>\\b\\d+(?:\\.\\d+)?\\s?(?:ms|µs|us|s|%|[KMG]?bits/sec|[KMG]?bit/s|Mbps|Gbps|MB|KB|GB)\\b)",
  ].join("|"), "gi");

  function renderLine(el, text) {
    el.textContent = "";
    if (text.startsWith("━━")) { el.className = "ln sect"; el.textContent = text; return; }
    el.className = "ln";
    if (text.length > 2000) { el.textContent = text; return; }
    let last = 0;
    for (const m of text.matchAll(HL)) {
      if (m.index > last) el.append(text.slice(last, m.index));
      const kind = Object.keys(m.groups).find((k) => m.groups[k] !== undefined);
      el.append(h("span", { class: `hl-${kind}` }, m[0]));
      last = m.index + m[0].length;
    }
    if (last < text.length) el.append(text.slice(last));
  }

  const MAX_DOM_LINES = 6000;

  function makeConsole(tool, hooks) {
    const statusDot = h("span", { class: "dot" });
    const statusText = h("span", null, "Ready");
    const timeEl = h("span", { class: "time" });
    const body = h("div", { class: `console-body ${store.get("wrap", false) ? "wrap" : ""}`, tabindex: "0", "aria-live": "off", role: "log" });
    const filter = h("input", { class: "input console-filter", placeholder: "Filter output…", type: "search", "aria-label": "Filter output" });
    let auto = true;
    const autoBtn = h("button", { class: "btn icon sm on", title: "Auto-scroll", "aria-label": "Toggle auto-scroll", "aria-pressed": "true" }, ic("scroll", "sm"));
    const wrapBtn = h("button", { class: `btn icon sm ${store.get("wrap", false) ? "on" : ""}`, title: "Wrap long lines", "aria-label": "Toggle line wrap" }, ic("wrap", "sm"));
    const copyBtn = h("button", { class: "btn icon sm", title: "Copy output", "aria-label": "Copy output" }, ic("copy", "sm"));
    const dlBtn = h("button", { class: "btn icon sm", title: "Download output", "aria-label": "Download output" }, ic("download", "sm"));
    const artifactBar = h("div", { class: "artifact", hidden: true });
    const el = h("section", { class: "card console" },
      h("div", { class: "console-bar" },
        h("div", { class: "console-status" }, statusDot, statusText, timeEl),
        h("span", { class: "spacer" }), filter, autoBtn, wrapBtn, copyBtn, dlBtn),
      body, artifactBar);

    const ctl = { el, jobId: null, es: null, timer: 0, lines: new Map(), first: 0, job: null };
    const empty = () => body.replaceChildren(h("div", { class: "console-empty" }, h("div", null, ic("terminal"),
      h("div", null, h("b", null, "Output appears here")), h("div", null, "Press ", h("kbd", null, "Ctrl"), " ", h("kbd", null, "Enter"), " or the Run button"))));
    empty();

    const setStatus = (job) => {
      ctl.job = job;
      const [cls, label] = STATUS[job.status] || ["", job.status];
      statusDot.className = `dot ${cls}`;
      statusText.textContent = job.exit_code != null && job.status !== "running" ? `${label} · exit ${job.exit_code}` : label;
      const running = job.status === "running";
      const tick = () => { timeEl.textContent = `${fmtTime(job.started)} · ${fmtDur((job.ended || Date.now() / 1000) - job.started)}`; };
      tick(); clearInterval(ctl.timer);
      if (running) ctl.timer = setInterval(tick, 1000);
      hooks.onState(running);
      if (job.artifact && !running) {
        artifactBar.hidden = false;
        artifactBar.replaceChildren(ic("folder", "sm"), h("span", null, "Saved "), h("code", null, job.artifact), h("span", { class: "spacer" }),
          h("button", { class: "btn sm", onclick: () => api(`/api/jobs/${job.id}/open`, { method: "POST", body: { action: "wireshark" } }).then(() => toast("ok", "Opening in Wireshark")).catch((e) => toast("fail", "Couldn't open", e.message)) }, ic("window", "sm"), "Open in Wireshark"),
          h("button", { class: "btn sm ghost", onclick: () => api(`/api/jobs/${job.id}/open`, { method: "POST", body: { action: "folder" } }).catch((e) => toast("fail", "Couldn't open", e.message)) }, "Show folder"));
      } else artifactBar.hidden = true;
    };

    const applyFilter = (lineEl) => {
      const q = filter.value.trim().toLowerCase();
      lineEl.classList.toggle("hidden", !!q && !lineEl.textContent.toLowerCase().includes(q));
    };
    const scroll = () => { if (auto) body.scrollTop = body.scrollHeight; };

    ctl.attach = (jobId, quiet) => {
      ctl.detach();
      ctl.jobId = jobId; ctl.lines = new Map(); ctl.first = 0;
      body.replaceChildren();
      const es = new EventSource(`/api/jobs/${jobId}/stream`);
      ctl.es = es;
      let pending = [], raf = 0, cmdShown = false, openIdx = -1;
      const flush = () => {
        raf = 0;
        const frag = document.createDocumentFragment();
        for (const [i, text] of pending) {
          let lineEl = ctl.lines.get(i);
          if (!lineEl) { lineEl = h("div"); ctl.lines.set(i, lineEl); frag.append(lineEl); }
          renderLine(lineEl, text);
          applyFilter(lineEl);
        }
        pending = [];
        body.append(frag);
        body.querySelectorAll(".open-line").forEach((x) => x.classList.remove("open-line"));
        if (openIdx >= 0 && ctl.lines.get(openIdx)) ctl.lines.get(openIdx).classList.add("open-line");
        while (ctl.lines.size > MAX_DOM_LINES) {
          const k = ctl.lines.keys().next().value;
          ctl.lines.get(k).remove(); ctl.lines.delete(k);
          if (!body.querySelector(".trim")) body.prepend(h("div", { class: "ln trim" }, "Earlier lines hidden — download the output for the full log."));
        }
        scroll();
      };
      es.addEventListener("meta", (ev) => {
        const job = JSON.parse(ev.data);
        setStatus(job);
        if (!cmdShown) { cmdShown = true; body.append(...job.command.map((c) => h("div", { class: "ln cmdline" }, c))); }
      });
      es.addEventListener("lines", (ev) => {
        const data = JSON.parse(ev.data);
        pending.push(...data.lines);
        openIdx = data.open && data.lines.length ? data.lines[data.lines.length - 1][0] : -1;
        if (!raf) raf = requestAnimationFrame(flush);
      });
      es.addEventListener("end", (ev) => {
        es.close();
        const job = JSON.parse(ev.data);
        openIdx = -1;
        if (raf) { cancelAnimationFrame(raf); } flush();
        setStatus(job);
        if (ctl.lines.size === 0) body.append(h("div", { class: "ln trim" }, "(no output)"));
        if (!quiet || job.ended > Date.now() / 1000 - 2) refreshJobs();
      });
      es.onerror = () => {
        if (es.readyState === EventSource.CLOSED && !ctl.job) {
          body.replaceChildren(h("div", { class: "console-empty" }, h("div", null, ic("clock"), h("div", null, "That run is no longer available."))));
          delete S.lastJob[tool.id]; store.set("lastJob", S.lastJob);
          hooks.onState(false); statusText.textContent = "Ready"; statusDot.className = "dot"; timeEl.textContent = "";
        }
      };
    };
    ctl.detach = () => { if (ctl.es) ctl.es.close(); ctl.es = null; clearInterval(ctl.timer); };
    ctl.stop = () => hooks.stop();

    body.addEventListener("scroll", () => {
      const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 30;
      if (auto !== atBottom) { auto = atBottom; autoBtn.classList.toggle("on", auto); autoBtn.setAttribute("aria-pressed", String(auto)); }
    });
    autoBtn.addEventListener("click", () => { auto = !auto; autoBtn.classList.toggle("on", auto); autoBtn.setAttribute("aria-pressed", String(auto)); scroll(); });
    wrapBtn.addEventListener("click", () => { const on = !body.classList.contains("wrap"); body.classList.toggle("wrap", on); wrapBtn.classList.toggle("on", on); store.set("wrap", on); });
    copyBtn.addEventListener("click", () => copyText([...ctl.lines.values()].map((x) => x.textContent).join("\n"), "Output copied"));
    dlBtn.addEventListener("click", () => { if (ctl.jobId) location.href = `/api/jobs/${ctl.jobId}/output`; });
    filter.addEventListener("input", () => ctl.lines.forEach(applyFilter));
    return ctl;
  }

  // ───────────────────────────────── activity ──────────────────────────────
  function viewActivity() {
    renderCrumbs([{ label: "Activity" }]);
    const tbody = h("tbody");
    const wrap = h("div", { class: "card" });
    const draw = () => {
      if (!S.jobs.length) {
        wrap.replaceChildren(h("div", { class: "empty" }, ic("clock"), h("b", null, "No runs yet"), "Tools you run appear here so you can revisit their output."));
        return;
      }
      tbody.replaceChildren(...S.jobs.map((j) => {
        const [cls, label] = STATUS[j.status] || ["", j.status];
        const dur = (j.ended || Date.now() / 1000) - j.started;
        const open = () => { location.hash = `#/t/${j.tool}?job=${j.id}`; };
        const stop = (e) => { e.stopPropagation(); api(`/api/jobs/${j.id}/stop`, { method: "POST" }).then(refreshJobs); };
        const del = (e) => { e.stopPropagation(); api(`/api/jobs/${j.id}`, { method: "DELETE" }).then(refreshJobs).catch((er) => toast("fail", er.message)); };
        const dl = (e) => { e.stopPropagation(); location.href = `/api/jobs/${j.id}/output`; };
        return h("tr", { onclick: open, tabindex: "0", onkeydown: (e) => { if (e.key === "Enter") open(); } },
          h("td", null, h("span", { class: "st" }, h("span", { class: `dot ${cls}` }), label)),
          h("td", null, h("b", null, j.name), j.elevated ? [" ", h("span", { class: "badge warn", title: "Ran with administrator rights" }, ic("key"))] : null),
          h("td", { class: "hide-sm" }, h("div", { class: "cmd", title: j.command.join("\n") }, j.command.join(" ; "))),
          h("td", { class: "num" }, fmtTime(j.started)),
          h("td", { class: "num hide-sm" }, fmtDur(dur)),
          h("td", null, h("div", { class: "acts" },
            j.status === "running" ? h("button", { class: "btn icon sm danger", title: "Stop", "aria-label": "Stop", onclick: stop }, ic("stop", "sm")) : null,
            h("button", { class: "btn icon sm ghost", title: "Download output", "aria-label": "Download output", onclick: dl }, ic("download", "sm")),
            j.status !== "running" ? h("button", { class: "btn icon sm ghost", title: "Remove", "aria-label": "Remove", onclick: del }, ic("trash", "sm")) : null)));
      }));
      wrap.replaceChildren(h("table", { class: "table" },
        h("thead", null, h("tr", null, h("th", null, "Status"), h("th", null, "Tool"), h("th", { class: "hide-sm" }, "Command"),
          h("th", null, "Started"), h("th", { class: "hide-sm" }, "Duration"), h("th", null, ""))), tbody));
    };
    draw();
    S.onJobs = draw;
    onCleanup(() => { S.onJobs = null; });
    const clearDone = async () => {
      await Promise.all(S.jobs.filter((j) => j.status !== "running").map((j) => api(`/api/jobs/${j.id}`, { method: "DELETE" }).catch(() => null)));
      refreshJobs();
    };
    return h("div", { class: "page" },
      h("div", { class: "page-head" }, h("div", { class: "grow" }, h("h1", null, "Activity"), h("p", null, "Every tool run in this session, newest first.")),
        h("button", { class: "btn", onclick: clearDone }, ic("trash"), "Clear finished")),
      wrap);
  }

  // ───────────────────────────────── settings ──────────────────────────────
  function viewSettings() {
    renderCrumbs([{ label: "Settings" }]);
    const page = h("div", { class: "page" }, h("div", { class: "page-head" }, h("div", { class: "grow" }, h("h1", null, "Settings"), h("p", null, "Appearance is saved in this browser; behaviour is saved to your NetDeck config."))));
    const grid = h("div", { class: "grid settings" });
    page.append(grid);
    const row = (title, desc, ctl) => h("div", { class: "set-row" }, h("div", { class: "txt" }, h("b", null, title), h("span", null, desc)), h("div", { class: "ctl" }, ctl));

    // appearance
    const themeSeg = h("div", { class: "seg" });
    ["system", "dark", "light"].forEach((v) => {
      const b = h("button", { type: "button", class: store.get("theme", "system") === v ? "on" : "" }, v[0].toUpperCase() + v.slice(1));
      b.addEventListener("click", () => { store.set("theme", v); applyTheme(); themeSeg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); });
      themeSeg.append(b);
    });
    const sw = h("div", { class: "swatches" });
    const curAccent = store.get("accent", null) || ACCENTS[0][0];
    ACCENTS.forEach(([c, name]) => {
      const b = h("button", { type: "button", class: `swatch ${c === curAccent ? "on" : ""}`, title: name, "aria-label": name });
      b.style.background = c;
      b.addEventListener("click", () => { store.set("accent", c === ACCENTS[0][0] ? null : c); applyTheme(); sw.querySelectorAll(".swatch").forEach((x) => x.classList.toggle("on", x === b)); });
      sw.append(b);
    });
    const size = h("input", { type: "range", min: "11", max: "16", step: "0.5", value: String(store.get("consoleSize", 12.5)), "aria-label": "Console font size" });
    size.addEventListener("input", () => { store.set("consoleSize", Number(size.value)); applyTheme(); });
    grid.append(h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Appearance")), h("div", { class: "card-body" },
      row("Theme", "Follow the system or force a theme.", themeSeg),
      row("Accent color", "Highlights, buttons and charts.", sw),
      row("Console text size", "Font size of tool output.", size))));

    // behaviour
    const behaviour = h("div", { class: "card-body" }, h("div", { class: "empty" }, h("div", { class: "spinner" })));
    grid.append(h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Behaviour")), behaviour));
    api("/api/settings").then((st) => {
      const save = async (patch) => {
        try {
          const res = await api("/api/settings", { method: "POST", body: patch });
          S.meta = res.meta; renderTopStatus(); toast("ok", "Settings saved");
        } catch (e) { toast("fail", "Couldn't save", e.message); }
      };
      const priv = h("select", { class: "input" }, [["auto", "Automatic"], ["pkexec", "polkit (pkexec)"], ["sudo", "sudo (passwordless)"], ["none", "Never elevate"]].map(([v, l]) => h("option", { value: v }, l)));
      priv.value = st.privilege; priv.addEventListener("change", () => save({ privilege: priv.value }));
      const term = h("select", { class: "input" }, h("option", { value: "auto" }, "Automatic"), st.terminals.map((n) => h("option", { value: n }, n)));
      term.value = st.terminals.includes(st.terminal) ? st.terminal : "auto";
      term.addEventListener("change", () => save({ terminal: term.value }));
      const appWin = h("input", { type: "checkbox" }); appWin.checked = st.app_window;
      appWin.addEventListener("change", () => save({ app_window: appWin.checked }));
      const cap = h("input", { class: "input", value: st.captures_dir, spellcheck: "false" });
      cap.addEventListener("change", () => save({ captures_dir: cap.value.trim() }));
      behaviour.replaceChildren(
        row("Administrator access", S.meta.privilege.description, priv),
        row("Terminal emulator", "Used for interactive tools like nmtui and bmon.", term),
        row("App window", "Open NetDeck in a chromeless window when Chrome/Chromium is installed.", h("label", { class: "switch" }, appWin, h("span", { class: "track" }))),
        row("Capture folder", "Where packet captures (.pcap) are saved.", cap),
      );
    }).catch((e) => behaviour.replaceChildren(h("div", { class: "callout fail" }, ic("alert"), e.message)));

    // about
    const installed = S.tools.filter((t) => t.installed).length;
    grid.append(h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "About")), h("div", { class: "card-body" },
      h("dl", { class: "kv" },
        h("dt", null, "Version"), h("dd", null, `NetDeck ${S.meta.version}`),
        h("dt", null, "Host"), h("dd", null, `${S.meta.hostname} (${S.meta.distro})`),
        h("dt", null, "Tools"), h("dd", null, `${installed} of ${S.tools.length} available`),
        h("dt", null, "Privileges"), h("dd", null, S.meta.privilege.mode),
        h("dt", null, "Terminal"), h("dd", null, S.meta.terminal || "none"),
        h("dt", null, "Captures"), h("dd", null, S.meta.captures_dir)),
      h("div", { class: "quick-row" }, h("span", { class: "help" }, "Run ", h("code", null, "netdeck doctor"), " in a terminal for a full dependency report.")))));
    return page;
  }

  // ───────────────────────────────── palette ───────────────────────────────
  const palette = { open: false, items: [], sel: 0 };
  function paletteEntries() {
    const pages = [
      { label: "Overview", sub: "Connection health and interfaces", icon: "home", href: "#/", cat: "Page" },
      { label: "Activity", sub: "All tool runs", icon: "clock", href: "#/activity", cat: "Page" },
      { label: "Settings", sub: "Theme, privileges, terminal", icon: "sliders", href: "#/settings", cat: "Page" },
      ...S.categories.map((c) => ({ label: c.name, sub: c.summary, icon: c.icon, href: `#/c/${c.id}`, cat: "Category" })),
    ];
    const tools = S.tools.map((t) => ({ label: t.name, sub: t.summary, icon: toolIcon(t), href: `#/t/${t.id}`, cat: catOf(t).name,
      hay: [t.name, t.summary, t.binary || "", catOf(t).name, ...(t.keywords || [])].join(" ").toLowerCase(), missing: !t.installed }));
    return [...tools, ...pages];
  }
  function score(entry, q) {
    const hay = entry.hay || `${entry.label} ${entry.sub}`.toLowerCase();
    const name = entry.label.toLowerCase();
    if (name.startsWith(q)) return 100;
    if (name.includes(q)) return 80;
    if (q.split(/\s+/).every((w) => hay.includes(w))) return 50;
    let i = 0; for (const ch of name) if (ch === q[i]) i++;
    return i === q.length ? 20 : 0;
  }
  function drawPalette() {
    const q = $("#palette-q").value.trim().toLowerCase();
    let items = paletteEntries();
    if (q) items = items.map((e) => [score(e, q), e]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).map(([, e]) => e);
    else items = [...S.tools.filter((t) => t.popular).map((t) => items.find((e) => e.href === `#/t/${t.id}`)), ...items.filter((e) => e.cat === "Page")];
    palette.items = items.slice(0, 40);
    palette.sel = Math.min(palette.sel, Math.max(0, palette.items.length - 1));
    const list = $("#palette-list");
    if (!palette.items.length) { list.replaceChildren(h("div", { class: "empty" }, "No matches")); return; }
    list.replaceChildren(...palette.items.map((e, i) => h("div", {
      class: `palette-item ${i === palette.sel ? "sel" : ""}`, role: "option", "aria-selected": String(i === palette.sel),
      onclick: () => choosePalette(i), onmousemove: () => { if (palette.sel !== i) { palette.sel = i; drawPalette(); } },
    }, h("div", { class: "tool-icon" }, ic(e.icon, "sm")), h("div", { class: "t" }, h("b", null, e.label), h("span", null, e.sub)),
    h("span", { class: "cat" }, e.missing ? "not installed" : e.cat))));
    const selEl = list.children[palette.sel];
    if (selEl) selEl.scrollIntoView({ block: "nearest" });
  }
  function openPalette() { palette.open = true; palette.sel = 0; $("#palette").classList.add("open"); $("#palette-q").value = ""; drawPalette(); $("#palette-q").focus(); }
  function closePalette() { palette.open = false; $("#palette").classList.remove("open"); }
  function choosePalette(i) { const e = palette.items[i]; closePalette(); if (e) location.hash = e.href; }

  // ───────────────────────────────── data ──────────────────────────────────
  async function refreshSystem() { S.system = await api("/api/system"); }
  async function refreshJobs() {
    try {
      S.jobs = (await api("/api/jobs")).jobs;
      const route = parseRoute();
      renderNav(route);
      if (S.onJobs) S.onJobs();
    } catch { /* transient */ }
  }

  async function boot() {
    applyTheme();
    $("#brand-logo").innerHTML = icon("pulse");
    $("#search-icon").innerHTML = icon("search", "sm");
    $("#palette-icon").innerHTML = icon("search");
    $("#menu-btn").innerHTML = icon("menu");
    try {
      const [meta, tools] = await Promise.all([api("/api/meta"), api("/api/tools"), refreshSystem()]);
      S.meta = meta; S.categories = tools.categories; S.tools = tools.tools;
      S.tools.forEach((t) => { S.byId[t.id] = t; });
    } catch (e) {
      $("#content").replaceChildren(h("div", { class: "empty" }, ic("alert"), h("b", null, "Couldn't reach NetDeck"), e.message));
      return;
    }
    renderTopStatus();
    window.addEventListener("hashchange", navigate);
    navigate();
    refreshJobs();
    setInterval(refreshJobs, 3000);

    $("#theme-btn").addEventListener("click", () => {
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      store.set("theme", dark ? "light" : "dark"); applyTheme();
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
    $("#menu-btn").addEventListener("click", () => $("#app").classList.toggle("nav-open"));
    $("#open-palette").addEventListener("click", openPalette);
    $("#palette").addEventListener("click", (e) => { if (e.target.id === "palette") closePalette(); });
    $("#palette-q").addEventListener("input", () => { palette.sel = 0; drawPalette(); });
    document.addEventListener("keydown", (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); palette.open ? closePalette() : openPalette(); return; }
      if (!palette.open && e.key === "/" && !typing) { e.preventDefault(); openPalette(); return; }
      if (!palette.open) return;
      if (e.key === "Escape") closePalette();
      else if (e.key === "ArrowDown") { e.preventDefault(); palette.sel = Math.min(palette.sel + 1, palette.items.length - 1); drawPalette(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); palette.sel = Math.max(palette.sel - 1, 0); drawPalette(); }
      else if (e.key === "Enter") { e.preventDefault(); choosePalette(palette.sel); }
    });
  }

  boot();
})();
