const state = {
  conversation: [],
  busy: false,
  healthTimer: null,
  lastResult: null,
  searchStudyCardsFirst: true,
  cardName: null,
  controller: null,
};

const elemts = {
  chatScroll: document.getElementById("chatScroll"),
  traceScroll: document.getElementById("traceScroll"),
  traceTime: document.getElementById("traceTime"),
  topbarNote: document.getElementById("topbarNote"),
  traceTitle: document.getElementById("traceTitle"),
  prompt: document.getElementById("prompt"),
  composer: document.getElementById("composer"),
  sendBtn: document.getElementById("sendBtn"),
  clearBtn: document.getElementById("clearBtn"),
  stopBtn: document.getElementById("stopBtn"),
  tabConversation: document.getElementById("tabConversation"),
  tabCardEditor: document.getElementById("tabCardEditor"),
  conversationView: document.getElementById("conversationView"),
  cardEditorView: document.getElementById("cardEditorView"),
  cardEditorSplit: document.getElementById("cardEditorSplit"),
  cardPaneToggle: document.getElementById("cardPaneToggle"),
  cardPreviewToggle: document.getElementById("cardPreviewToggle"),
  cardMarkdown: document.getElementById("cardMarkdown"),
  cardPreview: document.getElementById("cardPreview"),
  cardFolder: document.getElementById("cardFolder"),
  cardName: document.getElementById("cardName"),
  cardSaveBtn: document.getElementById("cardSaveBtn"),
  cardSaveStatus: document.getElementById("cardSaveStatus"),
  cardBrowserPanel: document.getElementById("cardBrowserPanel"),
  cardBrowserStatus: document.getElementById("cardBrowserStatus"),
  cardBrowserList: document.getElementById("cardBrowserList"),
  requestMeta: document.getElementById("requestMeta"),
  modelStatus: document.getElementById("modelStatus"),
  statusText: document.getElementById("statusText"),
  settingsBtn: document.getElementById("settingsBtn"),
  settingsOverlay: document.getElementById("settingsOverlay"),
  settingsClose: document.getElementById("settingsClose"),
  settingsCancel: document.getElementById("settingsCancel"),
  settingsForm: document.getElementById("settingsForm"),
  settingsScroll: document.getElementById("settingsScroll"),
  settingsStatus: document.getElementById("settingsStatus"),
  settingsSave: document.getElementById("settingsSave"),
  confirmOverlay: document.getElementById("confirmOverlay"),
  confirmMessage: document.getElementById("confirmMessage"),
  confirmCancel: document.getElementById("confirmCancel"),
  confirmOk: document.getElementById("confirmOk"),
  lightboxOverlay: document.getElementById("lightboxOverlay"),
  lightboxImage: document.getElementById("lightboxImage"),
  lightboxCaption: document.getElementById("lightboxCaption"),
  lightboxClose: document.getElementById("lightboxClose"),
};

const emptyTraceHTML = elemts.traceScroll.innerHTML;

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

function studyCardsToggleHTML() {
  const enabled = state.searchStudyCardsFirst;
  return `
    <div class="trace-block toggle-block">
      <label class="switch-row" for="studyCardsFirst">
        <span class="switch-copy">
          <span class="switch-title">Search study cards first</span>
          <span class="switch-hint">${enabled ? "Local cards are checked before the web." : "Study cards are skipped; search the web directly."}</span>
        </span>
        <span class="switch">
          <input type="checkbox" id="studyCardsFirst" role="switch" ${enabled ? "checked" : ""}>
          <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        </span>
      </label>
    </div>`;
}

function safeStatus(value) {
  return ["done", "failed", "skipped", "running"].includes(value) ? value : "done";
}

function safeKind(value) {
  return ["input", "plan", "tool", "read", "answer"].includes(value) ? value : "tool";
}

function renderInline(text) {
  return text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
}

function renderMarkdown(raw) {
  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
    return renderMarkdownLegacy(raw);
  }
  const html = marked.parse(String(raw ?? ""), { gfm: true, breaks: true });
  const safe = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
  return `<div class="markdown-body">${safe}</div>`;
}

function enhanceCodeBlocks(container) {
  container.querySelectorAll("pre > code").forEach((code) => {
    const pre = code.parentElement;
    const langClass = [...code.classList].find((name) => name.startsWith("language-"));
    const declared = langClass ? langClass.slice("language-".length).toLowerCase() : "";
    const language =
      declared && typeof hljs !== "undefined" && hljs.getLanguage(declared) ? declared : "";
    if (langClass) code.classList.remove(langClass);
    code.classList.add("hljs");
    if (language) code.classList.add(`language-${language}`);

    if (typeof hljs !== "undefined") {
      const source = code.textContent || "";
      code.innerHTML = language
        ? hljs.highlight(source, { language, ignoreIllegals: true }).value
        : hljs.highlightAuto(source).value;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "code-block";
    const head = document.createElement("div");
    head.className = "code-head";
    const label = document.createElement("span");
    label.textContent = language || declared || "code";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-code";
    button.textContent = "Copy";
    head.append(label, button);
    pre.replaceWith(wrapper);
    wrapper.append(head, pre);
  });
}

function enhanceImages(container) {
  container.querySelectorAll("img").forEach((img) => {
    img.classList.add("zoomable");
    img.tabIndex = 0;
    img.setAttribute("role", "button");
    img.setAttribute(
      "aria-label",
      img.alt ? `Open image preview: ${img.alt}` : "Open image preview"
    );
  });
}

function renderMarkdownLegacy(raw) {
  const codeBlocks = [];
  let text = String(raw ?? "").replace(/```([\w+.#-]*)[ \t]*\n?([\s\S]*?)```/g, (_, lang, code) => {
    const index = codeBlocks.length;
    const label = (lang || "code").toLowerCase();
    codeBlocks.push(
      `<div class="code-block"><div class="code-head"><span>${escapeHtml(label)}</span>` +
        '<button type="button" class="copy-code">Copy</button></div>' +
        `<pre><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre></div>`
    );
    return `\n@@CODEBLOCK${index}@@\n`;
  });

  text = escapeHtml(text);
  const lines = text.split("\n");
  const out = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };

  const closeList = () => {
    if (list) {
      out.push(`</${list}>`);
      list = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();

    const codeMatch = trimmed.match(/^@@CODEBLOCK(\d+)@@$/);
    if (codeMatch) {
      flushParagraph();
      closeList();
      out.push(codeBlocks[Number(codeMatch[1])] || "");
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      closeList();
      continue;
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      closeList();
      const level = heading[1].length;
      out.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      flushParagraph();
      if (list !== "ul") {
        closeList();
        out.push("<ul>");
        list = "ul";
      }
      out.push(`<li>${renderInline(bullet[1])}</li>`);
      continue;
    }

    const numbered = line.match(/^\s*\d+\.\s+(.*)$/);
    if (numbered) {
      flushParagraph();
      if (list !== "ol") {
        closeList();
        out.push("<ol>");
        list = "ol";
      }
      out.push(`<li>${renderInline(numbered[1])}</li>`);
      continue;
    }

    if (trimmed.startsWith("> ")) {
      flushParagraph();
      closeList();
      out.push(`<blockquote>${renderInline(trimmed.slice(2))}</blockquote>`);
      continue;
    }

    paragraph.push(trimmed);
  }

  flushParagraph();
  closeList();
  return `<div class="markdown-body">${out.join("")}</div>`;
}

function linkCitations(container, sources) {
  if (!Array.isArray(sources) || !sources.length) return;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);

  for (const node of nodes) {
    if (node.parentElement?.closest("pre, code, a, button")) continue;
    const value = node.nodeValue || "";
    if (!/\[\d+\]/.test(value)) continue;

    const fragment = document.createDocumentFragment();
    const pattern = /\[(\d+)\]/g;
    let last = 0;
    let match;
    let touched = false;

    while ((match = pattern.exec(value))) {
      const id = Number(match[1]);
      const source = sources[id - 1];
      if (!source) continue;
      touched = true;
      fragment.appendChild(document.createTextNode(value.slice(last, match.index)));
      const link = document.createElement("a");
      link.className = "cite";
      link.textContent = String(id);
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.title = source.title || source.domain || source.url;
      fragment.appendChild(link);
      last = match.index + match[0].length;
    }

    if (touched) {
      fragment.appendChild(document.createTextNode(value.slice(last)));
      node.parentElement.replaceChild(fragment, node);
    }
  }
}

function scrollChat() {
  requestAnimationFrame(() => {
    elemts.chatScroll.scrollTop = elemts.chatScroll.scrollHeight;
  });
}

function addMessage(role, content, options = {}) {
  const article = document.createElement("article");
  article.className = `msg ${role}`;

  const avatar = document.createElement("div");
  avatar.className = `avatar ${role === "user" ? "user-avatar" : "assistant-avatar"}`;
  avatar.textContent = role === "user" ? "User" : "SNL";

  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
    enhanceCodeBlocks(bubble);
    enhanceImages(bubble);
    linkCitations(bubble, options.sources || []);
  } else {
    bubble.innerHTML = `<p>${escapeHtml(content).replace(/\n/g, "<br>")}</p>`;
  }
  wrap.appendChild(bubble);

  if (options.meta?.length) {
    const meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.innerHTML = options.meta
      .map((item) => `<span>${escapeHtml(item)}</span>`)
      .join("");
    wrap.appendChild(meta);
  }

  const nodes = role === "user" ? [wrap, avatar] : [avatar, wrap];
  nodes.forEach((node) => article.appendChild(node));
  elemts.chatScroll.appendChild(article);
  scrollChat();
  return article;
}

function addLoadingMessage() {
  const article = document.createElement("article");
  article.className = "msg assistant";

  const avatar = document.createElement("div");
  avatar.className = "avatar assistant-avatar";
  avatar.textContent = "SNL";

  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML =
    '<span class="typing" aria-label="Working"><i></i><i></i><i></i></span>';

  wrap.appendChild(bubble);
  article.appendChild(avatar);
  article.appendChild(wrap);
  elemts.chatScroll.appendChild(article);
  scrollChat();
  return article;
}

function setTraceLoading() {
  elemts.traceTime.textContent = "…";
  const cardsFirst = state.searchStudyCardsFirst;
  const labels = cardsFirst
    ? ["Checking study cards", "Searching the web", "Reading sources", "Writing the answer"]
    : ["Searching the web", "Reading sources", "Writing the answer"];
  const kinds = cardsFirst ? ["tool", "tool", "read", "answer"] : ["tool", "read", "answer"];
  const summary = cardsFirst
    ? "Checking study_cards first, then querying DuckDuckGo and Brave if needed."
    : "Searching DuckDuckGo and Brave directly; study-card lookup is off.";
  elemts.traceScroll.innerHTML = `
    <div class="trace-block">
      <div class="block-head">
        <h3>Working</h3>
      </div>
      <p class="summary-text">${summary}</p>
    </div>
    ${studyCardsToggleHTML()}
    <div class="trace-block">
      <div class="block-head">
        <h3>Flow</h3>
      </div>
      <div class="flow">
        ${labels
          .map(
            (label, index) => `
          <div class="flow-item">
            <div class="flow-marker kind-${kinds[index]}" style="opacity:${1 - index * 0.16}">
              <span>${index + 1}</span>
            </div>
            <div class="flow-content">
              <div class="flow-title">${label}</div>
            </div>
          </div>`
          )
          .join("")}
      </div>
    </div>`;
}

function clearTrace() {
  elemts.traceScroll.innerHTML = emptyTraceHTML;
  elemts.traceTime.textContent = "—";
}

function renderTrace(result) {
  const elapsed = result.elapsed_ms ? `${(result.elapsed_ms / 1000).toFixed(1)}s` : "—";
  elemts.traceTime.textContent = elapsed;

  const sources = Array.isArray(result.sources) ? result.sources : [];
  const tools = Array.isArray(result.tools) ? result.tools : [];
  const steps = Array.isArray(result.steps) ? result.steps : [];
  const chips = [
    `${sources.length} source${sources.length === 1 ? "" : "s"}`,
    `${tools.length} tool${tools.length === 1 ? "" : "s"}`,
    `${steps.length} step${steps.length === 1 ? "" : "s"}`,
  ];
  if (result.llm_failed) chips.push("fallback");

  const summaryBlock = `
    <div class="trace-block">
      <div class="block-head">
        <h3>Summary</h3>
        <span class="block-count">${escapeHtml(elapsed)}</span>
      </div>
      <p class="summary-text">${escapeHtml(result.summary || "No summary available.")}</p>
      <div class="summary-chips">
        ${chips.map((chip) => `<span class="summary-chip">${escapeHtml(chip)}</span>`).join("")}
      </div>
    </div>`;

  const flowBlock = `
    <div class="trace-block">
      <div class="block-head">
        <h3>Flow</h3>
        <span class="block-count">${steps.length} nodes</span>
      </div>
      <div class="flow">
        ${steps
          .map((step, index) => {
            const kind = safeKind(step.kind);
            const status = safeStatus(step.status);
            return `
            <div class="flow-item">
              <div class="flow-marker kind-${kind} status-${status}">
                <span>${index + 1}</span>
              </div>
              <div class="flow-content">
                <div class="flow-title-row">
                  <span class="flow-title">${escapeHtml(step.label)}</span>
                  <span class="flow-status ${status}">${escapeHtml(status)}</span>
                </div>
                <div class="flow-detail">${escapeHtml(step.detail || "")}</div>
              </div>
            </div>`;
          })
          .join("")}
      </div>
    </div>`;

  const toolsBlock = `
    <div class="trace-block">
      <div class="block-head">
        <h3>Tools</h3>
        <span class="block-count">${tools.length}</span>
      </div>
      ${
        tools.length
          ? `<div class="tool-list">
              ${tools
                .map((tool) => {
                  const status = safeStatus(tool.status);
                  return `
                  <div class="tool-row status-${status}">
                    <div class="tool-name">
                      <span class="tool-dot"></span>
                      <span>${escapeHtml(tool.label || tool.name)}</span>
                    </div>
                    <span class="tool-detail">${escapeHtml(tool.detail || status)}</span>
                  </div>`;
                })
                .join("")}
            </div>`
          : '<p class="empty-note">No tools were used.</p>'
      }
    </div>`;

  const sourcesBlock = `
    <div class="trace-block">
      <div class="block-head">
        <h3>Sources</h3>
        <span class="block-count">${sources.length}</span>
      </div>
      ${
        sources.length
          ? `<div class="source-list">
              ${sources
                .map(
                  (source) => `
                <a class="source-row" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(source.snippet || source.title || source.url)}">
                  <span class="source-index">${escapeHtml(source.id)}</span>
                  <span class="source-main">
                    <span class="source-title">${escapeHtml(source.title || source.url)}</span>
                    <span class="source-meta">
                      <span>${escapeHtml(source.domain || "")}</span>
                      <span class="engine-tag ${escapeHtml(source.engine)}">${escapeHtml(source.engine || "web")}</span>
                      ${source.fetched ? "<span>read</span>" : ""}
                    </span>
                  </span>
                  <svg class="source-arrow" viewBox="0 0 24 24" width="13" height="13" fill="none" aria-hidden="true">
                    <path d="M7 17 17 7M9 7h8v8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </a>`
                )
                .join("")}
            </div>`
          : '<p class="empty-note">No sources were used for this answer.</p>'
      }
    </div>`;

  elemts.traceScroll.innerHTML =
    summaryBlock + studyCardsToggleHTML() + flowBlock + toolsBlock + sourcesBlock;
}

function setBusy(busy) {
  state.busy = busy;
  elemts.sendBtn.disabled = busy;
  elemts.prompt.setAttribute("aria-busy", String(busy));
}

async function sendMessage(value) {
  const text = String(value ?? elemts.prompt.value).trim();
  if (!text || state.busy) return;

  setBusy(true);
  addMessage("user", text);
  state.conversation.push({ role: "user", content: text });

  elemts.prompt.value = "";
  resizePrompt();
  const loading = addLoadingMessage();
  setTraceLoading();
  elemts.requestMeta.textContent = "Researching…";

  state.controller = new AbortController();
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: state.controller.signal,
      body: JSON.stringify({
        message: text,
        history: state.conversation.slice(0, -1).slice(-8),
        search_study_cards_first: state.searchStudyCardsFirst,
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.error) {
      throw new Error(result.error || `Request failed with HTTP ${response.status}`);
    }

    loading.remove();
    if (result.stopped) {
      elemts.requestMeta.textContent = "Stopped";
      return;
    }

    const seconds = result.elapsed_ms ? (result.elapsed_ms / 1000).toFixed(1) : "0.0";
    const meta = [
      `${result.sources?.length || 0} sources`,
      `${seconds}s`,
      result.llm_failed ? "fallback" : result.model || "MiniCPM5-2B",
    ];
    addMessage("assistant", result.answer, { sources: result.sources || [], meta });
    state.conversation.push({ role: "assistant", content: result.answer });
    state.lastResult = result;
    renderTrace(result);
    elemts.requestMeta.textContent = `${seconds}s · ${result.sources?.length || 0} sources`;
  } catch (error) {
    loading.remove();
    if (error?.name === "AbortError") {
      elemts.requestMeta.textContent = "Stopped";
      return;
    }
    const message = error instanceof Error ? error.message : String(error);
    addMessage("assistant", `I hit an error: ${message}`, { meta: ["error"] });
    elemts.traceTime.textContent = "—";
    elemts.traceScroll.innerHTML = `
      <div class="trace-block">
        <div class="block-head"><h3>Request failed</h3></div>
        <p class="empty-note">${escapeHtml(message)}</p>
      </div>`;
    elemts.requestMeta.textContent = "Request failed";
  } finally {
    state.controller = null;
    setBusy(false);
    elemts.prompt.focus();
  }
}

function resizePrompt() {
  elemts.prompt.style.height = "auto";
  elemts.prompt.style.height = `${Math.min(elemts.prompt.scrollHeight, 160)}px`;
}

function clearChat() {
  state.conversation = [];
  state.lastResult = null;
  elemts.chatScroll.querySelectorAll(".msg:not(.welcome)").forEach((node) => node.remove());
  clearTrace();
  elemts.requestMeta.textContent = "Local inference · no cloud";
  elemts.prompt.focus();
  scrollChat();
}

function updateStatus(health) {
  const status = health.status || "inactive";
  const model = health.model || "MiniCPM5-2B";
  elemts.modelStatus.dataset.state = health.loading ? "loading" : status;
  elemts.modelStatus.title = health.message || "";

  if (health.loading) {
    elemts.statusText.textContent = `Loading ${model}…`;
  } else if (status === "loading response") {
    elemts.statusText.textContent = `${model} · composing…`;
  } else if (status === "ready") {
    elemts.statusText.textContent = `${model} · ready`;
    if (!state.lastResult) {
      elemts.requestMeta.textContent = health.backend || "Local inference";
    }
  } else {
    elemts.statusText.textContent = `${model} · inactive`;
  }
}

async function checkHealth() {
  clearTimeout(state.healthTimer);
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    const health = await response.json();
    updateStatus(health);
    if (health.loading || health.status === "loading response") {
      state.healthTimer = setTimeout(checkHealth, 1500);
    } else if (health.status === "ready") {
      state.healthTimer = setTimeout(checkHealth, 30000);
    } else {
      state.healthTimer = setTimeout(checkHealth, 10000);
    }
  } catch (error) {
    updateStatus({ status: "inactive", message: "Backend unreachable" });
    state.healthTimer = setTimeout(checkHealth, 5000);
  }
}

elemts.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage();
});

elemts.prompt.addEventListener("input", resizePrompt);

elemts.prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    elemts.composer.requestSubmit();
  }
});

elemts.chatScroll.addEventListener("click", async (event) => {
  const suggestion = event.target.closest(".suggestion");
  if (suggestion) {
    sendMessage(suggestion.dataset.prompt || suggestion.textContent || "");
    return;
  }

  const image = event.target.closest("img.zoomable");
  if (image) {
    event.preventDefault();
    openLightbox(image);
    return;
  }

  const copyButton = event.target.closest(".copy-code");
  if (copyButton) {
    const code = copyButton.closest(".code-block")?.querySelector("code")?.innerText || "";
    try {
      await navigator.clipboard.writeText(code);
      const previous = copyButton.textContent;
      copyButton.textContent = "Copied";
      setTimeout(() => {
        copyButton.textContent = previous;
      }, 1200);
    } catch (error) {
      copyButton.textContent = "Copy failed";
      setTimeout(() => {
        copyButton.textContent = "Copy";
      }, 1200);
    }
  }
});

elemts.chatScroll.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const image = event.target.closest("img.zoomable");
  if (!image) return;
  event.preventDefault();
  openLightbox(image);
});

elemts.traceScroll.addEventListener("change", (event) => {
  const input = event.target.closest("#studyCardsFirst");
  if (!input) return;
  state.searchStudyCardsFirst = input.checked;
  const hint = input.closest(".switch-row")?.querySelector(".switch-hint");
  if (hint) {
    hint.textContent = input.checked
      ? "Local cards are checked before the web."
      : "Study cards are skipped; search the web directly.";
  }
});

elemts.clearBtn.addEventListener("click", clearChat);

function stopGeneration() {
  if (state.controller) {
    state.controller.abort();
  }
  fetch("/api/stop", { method: "POST", keepalive: true }).catch(() => {});
  setBusy(false);
  elemts.requestMeta.textContent = "Stopped";
}

elemts.stopBtn.addEventListener("click", stopGeneration);

function closeModelOnExit() {
  if (navigator.sendBeacon) {
    navigator.sendBeacon("/api/stop");
  } else {
    fetch("/api/stop", { method: "POST", keepalive: true }).catch(() => {});
  }
}

window.addEventListener("pagehide", closeModelOnExit);

function setActiveTab(tab) {
  const showConversation = tab === "conversation";
  elemts.tabConversation.classList.toggle("active", showConversation);
  elemts.tabConversation.setAttribute("aria-selected", String(showConversation));
  elemts.tabCardEditor.classList.toggle("active", !showConversation);
  elemts.tabCardEditor.setAttribute("aria-selected", String(!showConversation));
  elemts.conversationView.hidden = !showConversation;
  elemts.cardEditorView.hidden = showConversation;
  elemts.clearBtn.hidden = !showConversation;
  elemts.stopBtn.hidden = !showConversation;
  elemts.traceTitle.textContent = showConversation ? "Agent Trace" : "Card Browser";
  elemts.traceScroll.hidden = !showConversation;
  elemts.cardBrowserPanel.hidden = showConversation;
  if (!showConversation) {
    renderCardPreview();
    loadCardBrowser();
  }
}

elemts.tabConversation.addEventListener("click", () => setActiveTab("conversation"));
elemts.tabCardEditor.addEventListener("click", () => setActiveTab("cardeditor"));

const CARD_PREVIEW_EMPTY = '<p class="card-preview-empty">Rendered Markdown appears here.</p>';

function removeExtension(filename) {
  return (filename.substring(0, filename.lastIndexOf('.')) || filename);
}

function renderCardPreview() {
  const raw = elemts.cardMarkdown.value;
  if (!raw.trim()) {
    elemts.cardPreview.innerHTML = CARD_PREVIEW_EMPTY;
    return;
  }
  elemts.cardPreview.innerHTML = renderMarkdown(raw);
  enhanceCodeBlocks(elemts.cardPreview);
}

//function setCardStatus(text, kind) {
//  elemts.cardSaveStatus.textContent = text || "";
//  elemts.cardSaveStatus.className = `card-editor-status${kind ? ` ${kind}` : ""}`;
//}

elemts.cardMarkdown.addEventListener("input", renderCardPreview);

function setCardPaneCollapsed(collapsed) {
  elemts.cardEditorSplit.classList.toggle("source-collapsed", collapsed);
  elemts.cardPaneToggle.setAttribute("aria-expanded", String(!collapsed));
  elemts.cardPaneToggle.setAttribute(
    "aria-label",
    collapsed ? "Show markdown editor" : "Hide markdown editor"
  );
}

function setPreviewPaneCollapsed(collapsed) {
  elemts.cardEditorSplit.classList.toggle("preview-collapsed", collapsed);
  elemts.cardPreviewToggle.setAttribute("aria-expanded", String(!collapsed));
  elemts.cardPreviewToggle.setAttribute(
    "aria-label",
    collapsed ? "Show preview" : "Hide preview"
  );
}

elemts.cardPaneToggle.addEventListener("click", () => {
  setCardPaneCollapsed(!elemts.cardEditorSplit.classList.contains("source-collapsed"));
});

elemts.cardPreviewToggle.addEventListener("click", () => {
  setPreviewPaneCollapsed(!elemts.cardEditorSplit.classList.contains("preview-collapsed"));
});

elemts.cardSaveBtn.addEventListener("click", async () => {
  if (!elemts.cardMarkdown.value.trim()) {
    //setCardStatus("Nothing to save yet.", "error");
    setTopbarNote("Nothing to save yet.", "error");
    return;
  }
  elemts.cardSaveBtn.disabled = true;
  //setCardStatus("Saving…");
  setTopbarNote("Saving…");
  try {
    const response = await fetch("/api/study-card", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: elemts.cardMarkdown.value,
        name: removeExtension(elemts.cardName.value),
        folder: elemts.cardFolder.value.trim() || null,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Save failed (${response.status}).`);
    state.cardName = data.name;
    //setCardStatus("");
    //console.log(decodeURIComponent(data.path));
    setTopbarNote(`Saved to ${data.name}`, `Saved to ${decodeURIComponent(data.path)}`);
    loadCardBrowser();
  } catch (error) {
    setTopbarNote(error.message || "Save failed.", "error");
    //setCardStatus(error.message || "Save failed.", "error");
  } finally {
    elemts.cardSaveBtn.disabled = false;
  }
});

let topbarNoteTimer = null;

function setTopbarNote(text, title) {
  clearTimeout(topbarNoteTimer);
  elemts.topbarNote.textContent = text || "";
  elemts.topbarNote.title = title || text || "";
  elemts.topbarNote.hidden = !text;
  if (text) {
    topbarNoteTimer = setTimeout(() => {
      elemts.topbarNote.hidden = true;
    }, 6000);
  }
}

function setCardBrowserStatus(text, kind) {
  elemts.cardBrowserStatus.hidden = !text;
  elemts.cardBrowserStatus.textContent = text || "";
  elemts.cardBrowserStatus.className = `card-browser-status${kind ? ` ${kind}` : ""}`;
}

async function loadCardBrowser() {
  elemts.cardBrowserList.innerHTML = "";
  setCardBrowserStatus("Loading cards…");
  try {
    const response = await fetch("/api/study-cards");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Could not load cards (${response.status}).`);
    renderCardBrowser(
      Array.isArray(data.cards) ? data.cards : [],
      Array.isArray(data.folders) ? data.folders : []
    );
  } catch (error) {
    elemts.cardBrowserList.innerHTML = "";
    setCardBrowserStatus(error.message || "Could not load cards.", "error");
  }
}

function renderCardBrowser(cards, folders) {
  elemts.cardBrowserList.innerHTML = "";
  if (!cards.length && !folders.length) {
    setCardBrowserStatus("No markdown cards yet. Save one from the editor.");
    return;
  }
  setCardBrowserStatus("");

  const groups = new Map();
  groups.set("", []);
  for (const folder of folders) {
    if (!groups.has(folder)) groups.set(folder, []);
  }
  for (const card of cards) {
    const key = card.folder || "";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(card);
  }

  [...groups.keys()]
    .sort((a, b) => (a === "" ? -1 : b === "" ? 1 : a.localeCompare(b)))
    .forEach((folder) => {
      const group = document.createElement("div");
      group.className = "card-browser-group";
      const head = document.createElement("div");
      head.className = "card-browser-folder";
      head.textContent = folder || "study_cards/";
      group.appendChild(head);
      groups.get(folder).forEach((card) => {
        const item = document.createElement("div");
        item.className = "card-browser-item";
        item.dataset.path = card.path;

        const open = document.createElement("button");
        open.type = "button";
        open.className = "card-browser-open";
        open.innerHTML =
          '<span class="card-browser-dot" aria-hidden="true"></span>' +
          `<span class="card-browser-name">${escapeHtml(card.name)}</span>`;
        open.addEventListener("click", () => loadCardIntoEditor(card, item));

        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "card-browser-delete";
        remove.setAttribute("aria-label", `Delete ${card.name}`);
        remove.innerHTML =
          '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">' +
          '<path d="M18 6 6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        remove.addEventListener("click", () => confirmDeleteCard(card, item));

        item.append(open, remove);
        group.appendChild(item);
      });
      elemts.cardBrowserList.appendChild(group);
    });
}

async function loadCardIntoEditor(card, item) {
  try {
    const response = await fetch(card.url);
    if (!response.ok) throw new Error(`Could not open ${card.name} (${response.status}).`);
    elemts.cardMarkdown.value = await response.text();
    renderCardPreview();
    state.cardName = card.name;
    elemts.cardFolder.value = card.folder || "";
    elemts.cardName.value = card.name || "";
    elemts.cardBrowserList
      .querySelectorAll(".card-browser-item.active")
      .forEach((entry) => entry.classList.remove("active"));
    item.classList.add("active");
    setTopbarNote(`Loaded ${card.name}`, `Loaded ${card.path}`);
  } catch (error) {
    setCardBrowserStatus(error.message || "Could not open card.", "error");
  }
}

function confirmDeleteCard(card, item) {
  openConfirm(`Delete "${card.name}"? This cannot be undone.`, () => deleteCard(card, item));
}

async function deleteCard(card, item) {
  try {
    const response = await fetch("/api/study-card", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: card.path }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Delete failed (${response.status}).`);
    if (item.classList.contains("active")) {
      elemts.cardMarkdown.value = "";
      elemts.cardName.value = "";
      state.cardName = null;
      renderCardPreview();
    }
    setTopbarNote(`Deleted ${card.name}`);
    loadCardBrowser();
  } catch (error) {
    setCardBrowserStatus(error.message || "Could not delete card.", "error");
  }
}

function setSettingsStatus(text, kind) {
  elemts.settingsStatus.textContent = text || "";
  elemts.settingsStatus.className = `settings-status${kind ? ` ${kind}` : ""}`;
}

function buildSettingControl(field) {
  const id = `cfg-${field.key}`;
  const value = field.value ?? "";

  if (field.type === "bool") {
    const row = document.createElement("label");
    row.className = "switch-row config-bool";
    row.htmlFor = id;
    row.innerHTML = `
      <span class="switch-copy">
        <span class="switch-title">${escapeHtml(field.label)}${
          field.restart ? ' <span class="restart-tag">restart</span>' : ""
        }</span>
        <span class="switch-hint">${escapeHtml(field.hint || "")}</span>
      </span>
      <span class="switch">
        <input type="checkbox" id="${id}" data-key="${escapeHtml(field.key)}" data-type="bool" data-initial="${value === "1" ? "1" : "0"}" role="switch" ${value === "1" ? "checked" : ""}>
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
      </span>`;
    return row;
  }

  const wrap = document.createElement("div");
  wrap.className = "config-field";

  const labelRow = document.createElement("div");
  labelRow.className = "config-label-row";
  const label = document.createElement("label");
  label.className = "config-label";
  label.htmlFor = id;
  label.innerHTML = `${escapeHtml(field.label)}${
    field.restart ? ' <span class="restart-tag">restart</span>' : ""
  }`;
  labelRow.appendChild(label);

  if (field.type === "secret") {
    labelRow.insertAdjacentHTML(
      "beforeend",
      '<button type="button" class="ghost-btn secret-toggle">Show</button>'
    );
  }

  const input = document.createElement("input");
  input.id = id;
  input.dataset.key = field.key;
  input.dataset.type = field.type;
  input.dataset.initial = value;
  input.value = value;
  input.className = "config-input";
  if (field.type === "secret") {
    input.type = "password";
    input.autocomplete = "off";
    input.spellcheck = false;
  } else if (field.type === "int") {
    input.type = "number";
    input.min = field.min;
    input.max = field.max;
    input.step = "1";
  } else {
    input.type = "text";
    input.spellcheck = false;
  }

  const hint = document.createElement("p");
  hint.className = "config-hint";
  hint.textContent = field.hint || "";

  if (field.type === "secret") {
    const row = document.createElement("div");
    row.className = "secret-row";
    row.appendChild(input);
    wrap.append(labelRow, row, hint);
  } else {
    wrap.append(labelRow, input, hint);
  }
  return wrap;
}

function renderSettings(config) {
  elemts.settingsScroll.innerHTML = "";
  const groups = Array.isArray(config.groups) ? config.groups : [];
  if (!groups.length || !config.editable) {
    elemts.settingsScroll.innerHTML = `<p class="empty-note">${
      config.editable === false
        ? "python-dotenv is not installed, so settings cannot be edited here."
        : "No settings available."
    }</p>`;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const group of groups) {
    const section = document.createElement("section");
    section.className = "settings-group";
    const head = document.createElement("div");
    head.className = "settings-group-head";
    head.innerHTML = `
      <h3>${escapeHtml(group.name || "")}</h3>
      ${group.hint ? `<span>${escapeHtml(group.hint)}</span>` : ""}`;
    section.appendChild(head);
    for (const field of group.fields || []) {
      section.appendChild(buildSettingControl(field));
    }
    fragment.appendChild(section);
  }
  elemts.settingsScroll.appendChild(fragment);
}

async function openSettings() {
  elemts.settingsOverlay.hidden = false;
  elemts.settingsScroll.innerHTML = "";
  setSettingsStatus("Loading settings…");
  elemts.settingsSave.disabled = true;
  try {
    const response = await fetch("/api/config", { cache: "no-store" });
    const config = await response.json();
    if (!response.ok || config.error) {
      throw new Error(config.error || `HTTP ${response.status}`);
    }
    renderSettings(config);
    setSettingsStatus(config.env_exists ? "" : "No .env file yet — one will be created on save.");
    elemts.settingsSave.disabled = !config.editable;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    elemts.settingsScroll.innerHTML = `<p class="empty-note">${escapeHtml(message)}</p>`;
    setSettingsStatus("Could not load settings.", "error");
    elemts.settingsSave.disabled = false;
  }
}

function closeSettings() {
  elemts.settingsOverlay.hidden = true;
  setSettingsStatus("");
}

function collectSettings() {
  const values = {};
  elemts.settingsScroll.querySelectorAll("[data-key]").forEach((input) => {
    const key = input.dataset.key;
    const current = input.dataset.type === "bool" ? (input.checked ? "1" : "0") : input.value.trim();
    if (current !== input.dataset.initial) {
      values[key] = current;
    }
  });
  return values;
}

async function saveSettings(event) {
  event.preventDefault();
  const values = collectSettings();
  const keys = Object.keys(values);
  if (!keys.length) {
    setSettingsStatus("No changes to save.");
    return;
  }

  elemts.settingsSave.disabled = true;
  setSettingsStatus("Saving…");
  try {
    const response = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.error) {
      throw new Error(result.error || `HTTP ${response.status}`);
    }

    elemts.settingsScroll.querySelectorAll("[data-key]").forEach((input) => {
      if (input.dataset.key in values) {
        input.dataset.initial =
          input.dataset.type === "bool" ? (input.checked ? "1" : "0") : input.value.trim();
      }
    });

    if (result.restart_required) {
      setSettingsStatus(
        `Saved. Restart the app to apply: ${result.restart_keys.join(", ")}.`,
        "ok"
      );
    } else {
      setSettingsStatus("Saved — applied immediately.", "ok");
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setSettingsStatus(message, "error");
  } finally {
    elemts.settingsSave.disabled = false;
  }
}

elemts.settingsBtn.addEventListener("click", openSettings);
elemts.settingsClose.addEventListener("click", closeSettings);
elemts.settingsCancel.addEventListener("click", closeSettings);

elemts.settingsOverlay.addEventListener("click", (event) => {
  if (event.target === elemts.settingsOverlay) closeSettings();
});

let confirmAction = null;

function openConfirm(message, onConfirm) {
  confirmAction = onConfirm;
  elemts.confirmMessage.textContent = message;
  elemts.confirmOverlay.hidden = false;
  elemts.confirmOk.focus();
}

function closeConfirm() {
  elemts.confirmOverlay.hidden = true;
  confirmAction = null;
}

let lightboxReturnFocus = null;

function openLightbox(image) {
  lightboxReturnFocus = document.activeElement;
  elemts.lightboxImage.src = image.currentSrc || image.src;
  elemts.lightboxImage.alt = image.alt || "";
  const caption = (image.alt || "").trim();
  elemts.lightboxCaption.textContent = caption;
  elemts.lightboxCaption.hidden = !caption;
  elemts.lightboxOverlay.hidden = false;
  elemts.lightboxClose.focus();
}

function closeLightbox() {
  if (elemts.lightboxOverlay.hidden) return;
  elemts.lightboxOverlay.hidden = true;
  elemts.lightboxImage.removeAttribute("src");
  elemts.lightboxImage.alt = "";
  if (lightboxReturnFocus && typeof lightboxReturnFocus.focus === "function") {
    lightboxReturnFocus.focus();
  }
  lightboxReturnFocus = null;
}

elemts.lightboxClose.addEventListener("click", closeLightbox);

elemts.lightboxOverlay.addEventListener("click", (event) => {
  if (event.target === elemts.lightboxOverlay) closeLightbox();
});

elemts.confirmCancel.addEventListener("click", closeConfirm);

elemts.confirmOverlay.addEventListener("click", (event) => {
  if (event.target === elemts.confirmOverlay) closeConfirm();
});

elemts.confirmOk.addEventListener("click", () => {
  const action = confirmAction;
  closeConfirm();
  if (action) action();
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (!elemts.lightboxOverlay.hidden) {
    closeLightbox();
  } else if (!elemts.confirmOverlay.hidden) {
    closeConfirm();
  } else if (!elemts.settingsOverlay.hidden) {
    closeSettings();
  }
});

elemts.settingsForm.addEventListener("submit", saveSettings);

elemts.settingsScroll.addEventListener("click", (event) => {
  const toggle = event.target.closest(".secret-toggle");
  if (!toggle) return;
  const input = toggle.closest(".config-field")?.querySelector("input");
  if (!input) return;
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  toggle.textContent = show ? "Hide" : "Show";
});

resizePrompt();
checkHealth();
