"use strict";

const KEY = new URLSearchParams(location.search).get("key") || "";
const STAGES = ["idea", "shape", "draft", "test", "use"];
const STAGE_LABEL = { idea: "Idea", shape: "Shape", draft: "Draft", test: "Test", use: "Use" };

const app = document.getElementById("app");
const homeBtn = document.getElementById("home-btn");
homeBtn.addEventListener("click", () => showHome());

function withKey(path) {
  return path + (path.includes("?") ? "&" : "?") + "key=" + encodeURIComponent(KEY);
}

async function api(path, opts) {
  const res = await fetch(withKey(path), opts);
  let body = null;
  try { body = await res.json(); } catch (e) { body = null; }
  return { status: res.status, body };
}

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "onclick") node.addEventListener("click", v);
    else if (k === "html") node.innerHTML = v;
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c.nodeType ? c : document.createTextNode(c));
  return node;
}

// ---------------- Home ----------------

async function showHome() {
  homeBtn.hidden = true;
  app.innerHTML = "";
  const wrap = el("div", { class: "gallery" });
  wrap.append(el("h1", null, "My Skills"));
  const cards = el("div", { class: "cards" });
  const newCard = el("div", { class: "card new", onclick: startBuild }, "＋ Build a new skill");
  cards.append(newCard);

  const { body } = await api("/api/builds");
  for (const b of (body && body.builds) || []) {
    const card = el("div", { class: "card", onclick: () => openBuild(b.id) },
      el("div", null,
        el("div", { class: "title" }, b.title || "Untitled skill"),
        el("div", { class: "desc" }, "Stage: " + (STAGE_LABEL[b.stage] || b.stage))),
      el("span", { class: "pill " + b.status }, b.status));
    cards.append(card);
  }
  wrap.append(cards);
  app.append(wrap);
}

async function startBuild() {
  const { body } = await api("/api/builds", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (body && body.build) openBuild(body.build.id);
}

// ---------------- Build ----------------

let current = null; // {build, transcript}

async function openBuild(id) {
  const { body } = await api("/api/builds/" + id);
  if (!body || !body.build) return showHome();
  current = { build: body.build, transcript: body.transcript || [] };
  renderBuild();
}

function renderBuild() {
  homeBtn.hidden = false;
  app.innerHTML = "";
  const layout = el("div", { class: "layout" });
  layout.append(renderRail(), renderConversation(), renderPreview());
  app.append(layout);
  scrollMessages();
}

function renderRail() {
  const rail = el("div", { class: "rail" });
  const activeIdx = STAGES.indexOf(current.build.stage);
  STAGES.forEach((s, i) => {
    let cls = "step";
    if (i < activeIdx) cls += " done";
    if (i === activeIdx) cls += " active";
    const dot = el("span", { class: "dot" }, i < activeIdx ? "✓" : String(i + 1));
    rail.append(el("div", { class: cls }, dot, STAGE_LABEL[s]));
  });
  return rail;
}

function renderConversation() {
  const conv = el("div", { class: "conversation" });
  const messages = el("div", { class: "messages", id: "messages" });

  const hasIntro = current.transcript.some(e => e.role === "assistant");
  if (!hasIntro && current.build.stage === "idea") {
    messages.append(bubble("assistant",
      "Hi! Tell me what you'd like Claude to do better, and we'll turn it into a skill together."));
  }
  for (const e of current.transcript) {
    if (e.role === "user") messages.append(bubble("user", e.text));
    else if (e.role === "assistant" && e.chat_text) messages.append(bubble("assistant", e.chat_text));
  }
  conv.append(messages);
  conv.append(renderComposer());
  return conv;
}

function bubble(who, text) {
  return el("div", { class: "bubble " + who }, text);
}

function lastAssistant() {
  for (let i = current.transcript.length - 1; i >= 0; i--) {
    if (current.transcript[i].role === "assistant") return current.transcript[i];
  }
  return null;
}

function renderComposer() {
  const composer = el("div", { class: "composer", id: "composer" });
  const last = lastAssistant();
  const widget = last && last.widget;
  const allowText = !widget || widget.allow_free_text ||
    widget.type === "free_text" || current.build.stage === "idea";

  if (widget && widget.options && widget.options.length) {
    const choices = el("div", { class: "choices" });
    for (const opt of widget.options) {
      choices.append(el("button", { onclick: () => send({ choice_id: opt.id }) }, opt.label));
    }
    composer.append(choices);
  }
  if (allowText) {
    const ta = el("textarea", { placeholder: "Type your answer…", id: "composer-input" });
    ta.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); sendText(); }
    });
    const btn = el("button", { class: "primary", onclick: sendText }, "Send");
    composer.append(el("div", { class: "composer-row" }, ta, btn));
  }
  return composer;
}

function sendText() {
  const ta = document.getElementById("composer-input");
  const text = (ta && ta.value || "").trim();
  if (!text) return;
  send({ text });
}

async function send(payload) {
  const display = payload.text || (lastChoiceLabel(payload.choice_id)) || "…";
  current.transcript.push({ role: "user", text: display });
  const messages = document.getElementById("messages");
  messages.append(bubble("user", display));
  const spin = el("div", { class: "bubble assistant spinner" }, "Claude is thinking…");
  messages.append(spin);
  disableComposer(true);
  scrollMessages();

  const { status, body } = await api("/api/builds/" + current.build.id + "/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  spin.remove();

  if (status !== 200 || !body || body.error) {
    messages.append(errorCard(body && body.error, payload));
    disableComposer(false);
    scrollMessages();
    return;
  }
  current.build = body.build;
  current.transcript.push(body.turn);
  renderBuild();
}

function lastChoiceLabel(id) {
  const last = lastAssistant();
  if (last && last.widget) {
    const opt = (last.widget.options || []).find(o => o.id === id);
    if (opt) return opt.label;
  }
  return id;
}

function disableComposer(off) {
  document.querySelectorAll("#composer button, #composer textarea").forEach(n => n.disabled = off);
}

function errorCard(error, payload) {
  error = error || { message: "Something went wrong." };
  const card = el("div", { class: "error-card" });
  card.append(el("div", null, error.message || "Something went wrong."));
  if (error.detail) {
    const d = el("details");
    d.append(el("summary", null, "Details"), el("pre", null, String(error.detail)));
    card.append(d);
  }
  card.append(el("button", { class: "retry", onclick: () => { card.remove(); send(payload); } }, "Try again"));
  return card;
}

// ---------------- Preview ----------------

let previewMode = "friendly";

function renderPreview() {
  const panel = el("div", { class: "preview" });
  const last = lastAssistant();
  const preview = (last && last.skill_preview) || current.build.skillPreview || {};
  const draft = last && last.draft;

  panel.append(el("h3", null, "Skill preview"));
  panel.append(el("div", { class: "skill-name" }, preview.name || current.build.skill_name || "Your skill"));
  panel.append(el("div", { class: "skill-desc" }, preview.description || "Taking shape as you answer…"));

  if (draft) {
    const toggle = el("div", { class: "toggle" });
    const fBtn = el("button", { class: previewMode === "friendly" ? "active" : "" }, "Friendly");
    const mBtn = el("button", { class: previewMode === "markdown" ? "active" : "" }, "Markdown");
    fBtn.addEventListener("click", () => { previewMode = "friendly"; renderBuild(); });
    mBtn.addEventListener("click", () => { previewMode = "markdown"; renderBuild(); });
    toggle.append(fBtn, mBtn);
    panel.append(toggle);
    if (previewMode === "markdown") {
      panel.append(el("pre", { class: "markdown" }, draft));
    } else {
      for (const s of (preview.sections || [])) panel.append(el("div", { class: "section" }, s));
    }
  } else {
    for (const s of (preview.sections || [])) panel.append(el("div", { class: "section" }, s));
  }
  return panel;
}

function scrollMessages() {
  const m = document.getElementById("messages");
  if (m) m.scrollTop = m.scrollHeight;
}

// ---------------- boot ----------------
showHome();
