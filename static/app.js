const state = {
  conversation: [],
  busy: false,
  healthTimer: null,
  lastResult: null,
  searchStudyCardsFirst: true,
};

const els = {
  chatScroll: document.getElementById("chatScroll"),
  traceScroll: document.getElementById("traceScroll"),
  traceTime: document.getElementById("traceTime"),
  prompt: document.getElementById("prompt"),
  composer: document.getElementById("composer"),
  sendBtn: document.getElementById("sendBtn"),
  clearBtn: document.getElementById("clearBtn"),
  requestMeta: document.getElementById("requestMeta"),
  modelStatus: document.getElementById("modelStatus"),
  statusText: document.getElementById("statusText"),
};

const emptyTraceHTML = els.traceScroll.innerHTML;

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
    els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
  });
}

function addMessage(role, content, options = {}) {
  const article = document.createElement("article");
  article.className = `msg ${role}`;

  const avatar = document.createElement("div");
  avatar.className = `avatar ${role === "user" ? "user-avatar" : "assistant-avatar"}`;
  avatar.textContent = role === "user" ? "User" : "ML";

  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
    enhanceCodeBlocks(bubble);
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
  els.chatScroll.appendChild(article);
  scrollChat();
  return article;
}

function addLoadingMessage() {
  const article = document.createElement("article");
  article.className = "msg assistant";

  const avatar = document.createElement("div");
  avatar.className = "avatar assistant-avatar";
  avatar.textContent = "ML";

  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML =
    '<span class="typing" aria-label="Working"><i></i><i></i><i></i></span>';

  wrap.appendChild(bubble);
  article.appendChild(avatar);
  article.appendChild(wrap);
  els.chatScroll.appendChild(article);
  scrollChat();
  return article;
}

function setTraceLoading() {
  els.traceTime.textContent = "…";
  const cardsFirst = state.searchStudyCardsFirst;
  const labels = cardsFirst
    ? ["Checking study cards", "Searching the web", "Reading sources", "Writing the answer"]
    : ["Searching the web", "Reading sources", "Writing the answer"];
  const kinds = cardsFirst ? ["tool", "tool", "read", "answer"] : ["tool", "read", "answer"];
  const summary = cardsFirst
    ? "Checking study_cards first, then querying DuckDuckGo and Brave if needed."
    : "Searching DuckDuckGo and Brave directly; study-card lookup is off.";
  els.traceScroll.innerHTML = `
    <div class="trace-block">
      <div class="block-head">
        <h3>Working</h3>
        <span class="block-count">live</span>
      </div>
      <p class="summary-text">${summary}</p>
    </div>
    ${studyCardsToggleHTML()}
    <div class="trace-block">
      <div class="block-head">
        <h3>Flow</h3>
        <span class="block-count">live</span>
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
              <div class="flow-detail">waiting…</div>
            </div>
          </div>`
          )
          .join("")}
      </div>
    </div>`;
}

function clearTrace() {
  els.traceScroll.innerHTML = emptyTraceHTML;
  els.traceTime.textContent = "—";
}

function renderTrace(result) {
  const elapsed = result.elapsed_ms ? `${(result.elapsed_ms / 1000).toFixed(1)}s` : "—";
  els.traceTime.textContent = elapsed;

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

  els.traceScroll.innerHTML =
    summaryBlock + studyCardsToggleHTML() + flowBlock + toolsBlock + sourcesBlock;
}

function setBusy(busy) {
  state.busy = busy;
  els.sendBtn.disabled = busy;
  els.prompt.setAttribute("aria-busy", String(busy));
}

async function sendMessage(value) {
  const text = String(value ?? els.prompt.value).trim();
  if (!text || state.busy) return;

  setBusy(true);
  addMessage("user", text);
  state.conversation.push({ role: "user", content: text });

  els.prompt.value = "";
  resizePrompt();
  const loading = addLoadingMessage();
  setTraceLoading();
  els.requestMeta.textContent = "Researching…";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
    els.requestMeta.textContent = `${seconds}s · ${result.sources?.length || 0} sources`;
  } catch (error) {
    loading.remove();
    const message = error instanceof Error ? error.message : String(error);
    addMessage("assistant", `I hit an error: ${message}`, { meta: ["error"] });
    els.traceTime.textContent = "—";
    els.traceScroll.innerHTML = `
      <div class="trace-block">
        <div class="block-head"><h3>Request failed</h3></div>
        <p class="empty-note">${escapeHtml(message)}</p>
      </div>`;
    els.requestMeta.textContent = "Request failed";
  } finally {
    setBusy(false);
    els.prompt.focus();
  }
}

function resizePrompt() {
  els.prompt.style.height = "auto";
  els.prompt.style.height = `${Math.min(els.prompt.scrollHeight, 160)}px`;
}

function clearChat() {
  state.conversation = [];
  state.lastResult = null;
  els.chatScroll.querySelectorAll(".msg:not(.welcome)").forEach((node) => node.remove());
  clearTrace();
  els.requestMeta.textContent = "Local inference · no cloud";
  els.prompt.focus();
  scrollChat();
}

function updateStatus(health) {
  const status = health.status || (health.online ? "ready" : "error");
  els.modelStatus.dataset.state = status;
  els.modelStatus.title = health.message || "";

  if (status === "downloading" && health.progress > 0) {
    els.statusText.textContent = `Downloading MiniCPM5-2B · ${health.progress}%`;
  } else if (status === "loading" || status === "downloading" || status === "checking") {
    els.statusText.textContent = health.message || "Loading MiniCPM5-2B…";
  } else if (status === "ready") {
    els.statusText.textContent = `${health.model || "MiniCPM5-2B"} · ready`;
    if (!state.lastResult) {
      els.requestMeta.textContent = health.backend || "Local inference";
    }
  } else {
    els.statusText.textContent = "Model offline";
  }
}

async function checkHealth() {
  clearTimeout(state.healthTimer);
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    const health = await response.json();
    updateStatus(health);
    if (["downloading", "loading", "checking", "idle"].includes(health.status)) {
      state.healthTimer = setTimeout(checkHealth, 1500);
    } else if (health.status === "ready") {
      state.healthTimer = setTimeout(checkHealth, 30000);
    } else {
      state.healthTimer = setTimeout(checkHealth, 8000);
    }
  } catch (error) {
    updateStatus({ status: "error", message: "Backend unreachable" });
    state.healthTimer = setTimeout(checkHealth, 5000);
  }
}

els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage();
});

els.prompt.addEventListener("input", resizePrompt);

els.prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    els.composer.requestSubmit();
  }
});

els.chatScroll.addEventListener("click", async (event) => {
  const suggestion = event.target.closest(".suggestion");
  if (suggestion) {
    sendMessage(suggestion.dataset.prompt || suggestion.textContent || "");
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

els.traceScroll.addEventListener("change", (event) => {
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

els.clearBtn.addEventListener("click", clearChat);

resizePrompt();
checkHealth();
