/**
 * Inbound Bot Chat Widget
 *
 * A self-contained, embeddable chat widget that communicates with the
 * backend via WebSocket. No external dependencies required.
 *
 * Configuration is read from window.__INBOUND_BOT_CONFIG__ which is
 * set by the widget loader script (widget-loader.js.jinja2).
 */
(function () {
  "use strict";

  /* ------------------------------------------------------------------ */
  /*  Configuration                                                      */
  /* ------------------------------------------------------------------ */

  var cfg = window.__INBOUND_BOT_CONFIG__ || {};

  var CONFIG = {
    businessSlug: cfg.businessSlug || "",
    businessName: cfg.businessName || "Chat",
    wsUrl: cfg.wsUrl || "",
    primaryColor: cfg.primaryColor || "#1e40af",
    welcomeMessage: cfg.welcomeMessage || "Hi! How can we help you today?",
    position: cfg.position || "bottom-right",
    soundEnabled: cfg.soundEnabled !== undefined ? cfg.soundEnabled : true,
  };

  /* Compute a contrasting text colour for the primary button */
  function contrastColor(hex) {
    hex = hex.replace("#", "");
    if (hex.length === 3)
      hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    var r = parseInt(hex.substring(0, 2), 16);
    var g = parseInt(hex.substring(2, 4), 16);
    var b = parseInt(hex.substring(4, 6), 16);
    var luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.5 ? "#000000" : "#ffffff";
  }

  var TEXT_ON_PRIMARY = contrastColor(CONFIG.primaryColor);

  /* ------------------------------------------------------------------ */
  /*  Session storage helpers                                            */
  /* ------------------------------------------------------------------ */

  var STORAGE_KEY = "inbound_bot_messages_" + CONFIG.businessSlug;

  function loadMessages() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function saveMessages(messages) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch (_) {
      /* storage full or unavailable */
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Sound notification                                                 */
  /* ------------------------------------------------------------------ */

  var notificationSound = null;

  function playNotificationSound() {
    if (!CONFIG.soundEnabled) return;
    try {
      if (!notificationSound) {
        /* Generate a short beep via AudioContext */
        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        var ctx = new AudioCtx();
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.value = 880;
        gain.gain.value = 0.15;
        osc.start();
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
        osc.stop(ctx.currentTime + 0.3);
        return; /* played inline */
      }
    } catch (_) {
      /* audio not available */
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Styles (injected into Shadow DOM or document head)                 */
  /* ------------------------------------------------------------------ */

  function buildStyles() {
    var pc = CONFIG.primaryColor;
    var tp = TEXT_ON_PRIMARY;
    var pos = CONFIG.position;
    var isLeft = pos.indexOf("left") !== -1;

    return (
      '\n/* ---- Inbound Bot Widget Styles ---- */\n' +
      ':host, .inbound-bot-root {\n  all: initial;\n  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;\n  font-size: 14px;\n  line-height: 1.5;\n  color: #1f2937;\n  box-sizing: border-box;\n}\n' +
      '*, *::before, *::after { box-sizing: border-box; }\n' +
      /* Toggle button */
      '.inbound-bot-toggle {\n' +
      '  position: fixed;\n  bottom: 20px;\n  ' +
      (isLeft ? "left: 20px;" : "right: 20px;") +
      '\n  width: 60px;\n  height: 60px;\n  border-radius: 50%;\n' +
      '  background: ' + pc + ';\n  color: ' + tp + ';\n' +
      '  border: none;\n  cursor: pointer;\n  box-shadow: 0 4px 12px rgba(0,0,0,0.2);\n' +
      '  display: flex;\n  align-items: center;\n  justify-content: center;\n' +
      '  z-index: 2147483646;\n  transition: transform 0.2s ease, box-shadow 0.2s ease;\n' +
      '  outline: none;\n  padding: 0;\n}\n' +
      '.inbound-bot-toggle:hover { transform: scale(1.08); box-shadow: 0 6px 18px rgba(0,0,0,0.25); }\n' +
      '.inbound-bot-toggle:focus-visible { outline: 3px solid ' + pc + '; outline-offset: 3px; }\n' +
      '.inbound-bot-toggle svg { width: 28px; height: 28px; fill: ' + tp + '; }\n' +
      /* Pulse animation on first load */
      '@keyframes inbound-bot-pulse {\n  0% { box-shadow: 0 0 0 0 ' + pc + '80; }\n  70% { box-shadow: 0 0 0 14px ' + pc + '00; }\n  100% { box-shadow: 0 0 0 0 ' + pc + '00; }\n}\n' +
      '.inbound-bot-toggle--pulse { animation: inbound-bot-pulse 2s ease 3; }\n' +
      /* Chat panel */
      '.inbound-bot-panel {\n' +
      '  position: fixed;\n  bottom: 90px;\n  ' +
      (isLeft ? "left: 20px;" : "right: 20px;") +
      '\n  width: 400px;\n  height: 600px;\n  max-height: calc(100vh - 120px);\n' +
      '  background: #ffffff;\n  border-radius: 16px;\n' +
      '  box-shadow: 0 8px 30px rgba(0,0,0,0.18);\n  display: flex;\n  flex-direction: column;\n' +
      '  overflow: hidden;\n  z-index: 2147483647;\n  opacity: 0;\n  transform: translateY(20px) scale(0.95);\n' +
      '  transition: opacity 0.25s ease, transform 0.25s ease;\n  pointer-events: none;\n}\n' +
      '.inbound-bot-panel--open {\n  opacity: 1;\n  transform: translateY(0) scale(1);\n  pointer-events: auto;\n}\n' +
      /* Header */
      '.inbound-bot-header {\n' +
      '  background: ' + pc + ';\n  color: ' + tp + ';\n  padding: 16px 16px;\n  display: flex;\n' +
      '  align-items: center;\n  justify-content: space-between;\n  flex-shrink: 0;\n}\n' +
      '.inbound-bot-header-title {\n  font-size: 16px;\n  font-weight: 600;\n  margin: 0;\n  white-space: nowrap;\n  overflow: hidden;\n  text-overflow: ellipsis;\n}\n' +
      '.inbound-bot-header-actions { display: flex; gap: 8px; flex-shrink: 0; }\n' +
      '.inbound-bot-header-btn {\n  background: none;\n  border: none;\n  cursor: pointer;\n  color: ' + tp + ';\n  padding: 4px;\n  border-radius: 4px;\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  opacity: 0.8;\n  transition: opacity 0.15s;\n  outline: none;\n}\n' +
      '.inbound-bot-header-btn:hover { opacity: 1; }\n' +
      '.inbound-bot-header-btn:focus-visible { outline: 2px solid ' + tp + '; outline-offset: 1px; }\n' +
      '.inbound-bot-header-btn svg { width: 18px; height: 18px; fill: ' + tp + '; }\n' +
      /* Messages area */
      '.inbound-bot-messages {\n' +
      '  flex: 1;\n  overflow-y: auto;\n  padding: 16px;\n  display: flex;\n  flex-direction: column;\n  gap: 10px;\n  scroll-behavior: smooth;\n}\n' +
      '.inbound-bot-msg {\n  max-width: 82%;\n  padding: 10px 14px;\n  border-radius: 16px;\n  word-wrap: break-word;\n  white-space: pre-wrap;\n  font-size: 14px;\n  line-height: 1.45;\n  animation: inbound-bot-fadeIn 0.2s ease;\n}\n' +
      '@keyframes inbound-bot-fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }\n' +
      '.inbound-bot-msg--bot {\n  align-self: flex-start;\n  background: #f3f4f6;\n  color: #1f2937;\n  border-bottom-left-radius: 4px;\n}\n' +
      '.inbound-bot-msg--user {\n  align-self: flex-end;\n  background: ' + pc + ';\n  color: ' + tp + ';\n  border-bottom-right-radius: 4px;\n}\n' +
      /* Typing indicator */
      '.inbound-bot-typing {\n  display: none;\n  align-self: flex-start;\n  padding: 10px 16px;\n  background: #f3f4f6;\n  border-radius: 16px;\n  border-bottom-left-radius: 4px;\n  gap: 4px;\n  align-items: center;\n}\n' +
      '.inbound-bot-typing--visible { display: flex; }\n' +
      '.inbound-bot-typing-dot {\n  width: 7px;\n  height: 7px;\n  background: #9ca3af;\n  border-radius: 50%;\n  animation: inbound-bot-typingBounce 1.4s ease-in-out infinite;\n}\n' +
      '.inbound-bot-typing-dot:nth-child(2) { animation-delay: 0.2s; }\n' +
      '.inbound-bot-typing-dot:nth-child(3) { animation-delay: 0.4s; }\n' +
      '@keyframes inbound-bot-typingBounce {\n  0%, 60%, 100% { transform: translateY(0); }\n  30% { transform: translateY(-6px); }\n}\n' +
      /* Input area */
      '.inbound-bot-input-area {\n' +
      '  display: flex;\n  padding: 12px;\n  border-top: 1px solid #e5e7eb;\n  background: #ffffff;\n  flex-shrink: 0;\n  gap: 8px;\n  align-items: flex-end;\n}\n' +
      '.inbound-bot-input {\n' +
      '  flex: 1;\n  border: 1px solid #d1d5db;\n  border-radius: 12px;\n  padding: 10px 14px;\n  font-size: 14px;\n  line-height: 1.4;\n  resize: none;\n  outline: none;\n  font-family: inherit;\n  max-height: 100px;\n  min-height: 40px;\n  transition: border-color 0.15s;\n  background: #ffffff;\n  color: #1f2937;\n}\n' +
      '.inbound-bot-input:focus { border-color: ' + pc + '; }\n' +
      '.inbound-bot-input::placeholder { color: #9ca3af; }\n' +
      '.inbound-bot-input:disabled { background: #f9fafb; cursor: not-allowed; }\n' +
      '.inbound-bot-send {\n' +
      '  width: 40px;\n  height: 40px;\n  border-radius: 50%;\n  background: ' + pc + ';\n  color: ' + tp + ';\n' +
      '  border: none;\n  cursor: pointer;\n  display: flex;\n  align-items: center;\n  justify-content: center;\n' +
      '  flex-shrink: 0;\n  transition: opacity 0.15s, transform 0.15s;\n  outline: none;\n  padding: 0;\n}\n' +
      '.inbound-bot-send:hover { transform: scale(1.05); }\n' +
      '.inbound-bot-send:focus-visible { outline: 3px solid ' + pc + '; outline-offset: 2px; }\n' +
      '.inbound-bot-send:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }\n' +
      '.inbound-bot-send svg { width: 18px; height: 18px; fill: ' + tp + '; }\n' +
      /* Powered-by */
      '.inbound-bot-powered {\n  text-align: center;\n  font-size: 11px;\n  color: #9ca3af;\n  padding: 4px 0 8px;\n  flex-shrink: 0;\n  background: #ffffff;\n}\n' +
      /* Mobile responsive */
      '@media (max-width: 639px) {\n' +
      '  .inbound-bot-panel {\n    width: 100vw;\n    height: 100vh;\n    max-height: 100vh;\n    bottom: 0;\n    left: 0;\n    right: 0;\n    border-radius: 0;\n    top: 0;\n  }\n' +
      '  .inbound-bot-panel--open { transform: translateY(0) scale(1); }\n' +
      '}\n' +
      /* Dark mode support */
      '@media (prefers-color-scheme: dark) {\n' +
      '  .inbound-bot-panel { background: #1f2937; }\n' +
      '  .inbound-bot-msg--bot { background: #374151; color: #f3f4f6; }\n' +
      '  .inbound-bot-typing { background: #374151; }\n' +
      '  .inbound-bot-typing-dot { background: #6b7280; }\n' +
      '  .inbound-bot-input-area { background: #1f2937; border-top-color: #374151; }\n' +
      '  .inbound-bot-input { background: #111827; color: #f3f4f6; border-color: #4b5563; }\n' +
      '  .inbound-bot-input::placeholder { color: #6b7280; }\n' +
      '  .inbound-bot-input:disabled { background: #1f2937; }\n' +
      '  .inbound-bot-powered { background: #1f2937; color: #6b7280; }\n' +
      '  .inbound-bot-messages::-webkit-scrollbar-track { background: #1f2937; }\n' +
      '  .inbound-bot-messages::-webkit-scrollbar-thumb { background: #4b5563; }\n' +
      '}\n' +
      /* Scrollbar styling */
      '.inbound-bot-messages::-webkit-scrollbar { width: 6px; }\n' +
      '.inbound-bot-messages::-webkit-scrollbar-track { background: transparent; }\n' +
      '.inbound-bot-messages::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }\n' +
      '.inbound-bot-messages::-webkit-scrollbar-thumb:hover { background: #9ca3af; }\n'
    );
  }

  /* ------------------------------------------------------------------ */
  /*  SVG Icons                                                          */
  /* ------------------------------------------------------------------ */

  var ICON_CHAT =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h10v2H7zm0-3h10v2H7zm0 6h7v2H7z"/></svg>';

  var ICON_CLOSE =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';

  var ICON_MINIMIZE =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19 13H5v-2h14v2z"/></svg>';

  var ICON_SEND =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

  /* ------------------------------------------------------------------ */
  /*  DOM Construction                                                   */
  /* ------------------------------------------------------------------ */

  var root, shadow, container;
  var toggleBtn, panel, messagesEl, typingEl, inputEl, sendBtn;
  var isOpen = false;
  var ws = null;
  var wsConnected = false;
  var retryCount = 0;
  var MAX_RETRIES = 5;
  var retryTimer = null;
  var isWaiting = false;
  var messages = loadMessages();
  var firstMessageSent = false;
  var sessionId = null;

  function buildWidget() {
    /* Root container */
    root = document.createElement("div");
    root.setAttribute("id", "inbound-bot-widget");

    /* Use Shadow DOM if available */
    if (root.attachShadow) {
      shadow = root.attachShadow({ mode: "open" });
      container = shadow;
    } else {
      container = root;
    }

    /* Inject styles */
    var styleEl = document.createElement("style");
    styleEl.textContent = buildStyles();
    container.appendChild(styleEl);

    /* Inner wrapper for CSS scoping fallback */
    var wrapper = document.createElement("div");
    wrapper.className = "inbound-bot-root";
    container.appendChild(wrapper);

    /* Toggle button */
    toggleBtn = document.createElement("button");
    toggleBtn.className = "inbound-bot-toggle inbound-bot-toggle--pulse";
    toggleBtn.setAttribute("aria-label", "Open chat");
    toggleBtn.setAttribute("role", "button");
    toggleBtn.setAttribute("tabindex", "0");
    toggleBtn.innerHTML = ICON_CHAT;
    wrapper.appendChild(toggleBtn);

    /* Remove pulse after animation completes */
    setTimeout(function () {
      toggleBtn.classList.remove("inbound-bot-toggle--pulse");
    }, 6500);

    /* Chat panel */
    panel = document.createElement("div");
    panel.className = "inbound-bot-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Chat window");
    panel.setAttribute("aria-hidden", "true");

    /* Header */
    var header = document.createElement("div");
    header.className = "inbound-bot-header";

    var title = document.createElement("h2");
    title.className = "inbound-bot-header-title";
    title.textContent = CONFIG.businessName;
    header.appendChild(title);

    var headerActions = document.createElement("div");
    headerActions.className = "inbound-bot-header-actions";

    var minimizeBtn = document.createElement("button");
    minimizeBtn.className = "inbound-bot-header-btn";
    minimizeBtn.setAttribute("aria-label", "Minimize chat");
    minimizeBtn.setAttribute("tabindex", "0");
    minimizeBtn.innerHTML = ICON_MINIMIZE;
    minimizeBtn.addEventListener("click", closePanel);
    headerActions.appendChild(minimizeBtn);

    var closeBtn = document.createElement("button");
    closeBtn.className = "inbound-bot-header-btn";
    closeBtn.setAttribute("aria-label", "Close chat");
    closeBtn.setAttribute("tabindex", "0");
    closeBtn.innerHTML = ICON_CLOSE;
    closeBtn.addEventListener("click", closePanel);
    headerActions.appendChild(closeBtn);

    header.appendChild(headerActions);
    panel.appendChild(header);

    /* Messages area */
    messagesEl = document.createElement("div");
    messagesEl.className = "inbound-bot-messages";
    messagesEl.setAttribute("role", "log");
    messagesEl.setAttribute("aria-live", "polite");
    messagesEl.setAttribute("aria-label", "Chat messages");
    panel.appendChild(messagesEl);

    /* Typing indicator */
    typingEl = document.createElement("div");
    typingEl.className = "inbound-bot-typing";
    typingEl.setAttribute("aria-label", "Bot is typing");
    for (var d = 0; d < 3; d++) {
      var dot = document.createElement("span");
      dot.className = "inbound-bot-typing-dot";
      typingEl.appendChild(dot);
    }
    messagesEl.appendChild(typingEl);

    /* Input area */
    var inputArea = document.createElement("div");
    inputArea.className = "inbound-bot-input-area";

    inputEl = document.createElement("textarea");
    inputEl.className = "inbound-bot-input";
    inputEl.setAttribute("placeholder", "Type a message...");
    inputEl.setAttribute("aria-label", "Message input");
    inputEl.setAttribute("rows", "1");
    inputEl.setAttribute("tabindex", "0");
    inputArea.appendChild(inputEl);

    sendBtn = document.createElement("button");
    sendBtn.className = "inbound-bot-send";
    sendBtn.setAttribute("aria-label", "Send message");
    sendBtn.setAttribute("tabindex", "0");
    sendBtn.innerHTML = ICON_SEND;
    inputArea.appendChild(sendBtn);

    panel.appendChild(inputArea);

    /* Powered-by */
    var powered = document.createElement("div");
    powered.className = "inbound-bot-powered";
    powered.textContent = "Powered by Inbound Bot";
    panel.appendChild(powered);

    wrapper.appendChild(panel);

    /* Append to body */
    document.body.appendChild(root);

    /* Restore saved messages */
    renderSavedMessages();

    /* Event listeners */
    toggleBtn.addEventListener("click", togglePanel);
    sendBtn.addEventListener("click", sendMessage);

    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    /* Auto-resize textarea */
    inputEl.addEventListener("input", function () {
      inputEl.style.height = "auto";
      inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + "px";
    });

    /* Close panel on Escape */
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isOpen) {
        closePanel();
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /*  Panel open / close                                                 */
  /* ------------------------------------------------------------------ */

  function togglePanel() {
    if (isOpen) {
      closePanel();
    } else {
      openPanel();
    }
  }

  function openPanel() {
    isOpen = true;
    panel.classList.add("inbound-bot-panel--open");
    panel.setAttribute("aria-hidden", "false");
    toggleBtn.setAttribute("aria-label", "Close chat");
    toggleBtn.innerHTML = ICON_CLOSE;
    inputEl.focus();
    scrollToBottom();

    /* Lazy WebSocket connection */
    if (!ws && !wsConnected) {
      connectWebSocket();
    }
  }

  function closePanel() {
    isOpen = false;
    panel.classList.remove("inbound-bot-panel--open");
    panel.setAttribute("aria-hidden", "true");
    toggleBtn.setAttribute("aria-label", "Open chat");
    toggleBtn.innerHTML = ICON_CHAT;
    toggleBtn.focus();
  }

  /* ------------------------------------------------------------------ */
  /*  Message rendering                                                  */
  /* ------------------------------------------------------------------ */

  function addMessageToUI(role, text) {
    var msgEl = document.createElement("div");
    msgEl.className =
      "inbound-bot-msg " +
      (role === "user" ? "inbound-bot-msg--user" : "inbound-bot-msg--bot");
    msgEl.textContent = text;
    msgEl.setAttribute("role", "listitem");

    /* Insert before typing indicator */
    messagesEl.insertBefore(msgEl, typingEl);
    scrollToBottom();
  }

  function renderSavedMessages() {
    for (var i = 0; i < messages.length; i++) {
      addMessageToUI(messages[i].role, messages[i].content);
    }
  }

  function scrollToBottom() {
    requestAnimationFrame(function () {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  function showTyping() {
    typingEl.classList.add("inbound-bot-typing--visible");
    scrollToBottom();
  }

  function hideTyping() {
    typingEl.classList.remove("inbound-bot-typing--visible");
  }

  function setInputDisabled(disabled) {
    isWaiting = disabled;
    inputEl.disabled = disabled;
    sendBtn.disabled = disabled;
  }

  /* ------------------------------------------------------------------ */
  /*  WebSocket connection                                               */
  /* ------------------------------------------------------------------ */

  function connectWebSocket() {
    if (!CONFIG.wsUrl) {
      addMessageToUI("bot", "Chat is not configured properly. Please contact support.");
      return;
    }

    try {
      ws = new WebSocket(CONFIG.wsUrl);
    } catch (e) {
      addMessageToUI("bot", "Unable to connect. Please try again later.");
      return;
    }

    ws.onopen = function () {
      wsConnected = true;
      retryCount = 0;
    };

    ws.onmessage = function (event) {
      hideTyping();
      setInputDisabled(false);

      try {
        var data = JSON.parse(event.data);
        var type = data.type || "message";
        var content = data.content || "";

        /* Capture session_id from server */
        if (data.session_id) {
          sessionId = data.session_id;
        }

        if (type === "error") {
          addMessageToUI("bot", content || "Something went wrong. Please try again.");
        } else if (type === "message" && content) {
          var msg = { role: "bot", content: content };
          messages.push(msg);
          saveMessages(messages);
          addMessageToUI("bot", content);
          playNotificationSound();
        }
      } catch (_) {
        /* Fallback: treat as plain text */
        var fallback = event.data || "";
        if (fallback) {
          var fmsg = { role: "bot", content: fallback };
          messages.push(fmsg);
          saveMessages(messages);
          addMessageToUI("bot", fallback);
        }
      }
    };

    ws.onerror = function () {
      /* handled by onclose */
    };

    ws.onclose = function (event) {
      wsConnected = false;
      ws = null;

      /* Do not reconnect on explicit close from server (business not found) */
      if (event.code === 4004) {
        addMessageToUI("bot", "This chat is currently unavailable.");
        return;
      }

      /* Exponential backoff reconnection */
      if (retryCount < MAX_RETRIES) {
        retryCount++;
        var delay = Math.min(1000 * Math.pow(2, retryCount - 1), 30000);
        retryTimer = setTimeout(function () {
          if (isOpen) {
            connectWebSocket();
          }
        }, delay);
      } else {
        addMessageToUI(
          "bot",
          "Connection lost. Please refresh the page to reconnect."
        );
      }
    };
  }

  /* ------------------------------------------------------------------ */
  /*  Sending messages                                                   */
  /* ------------------------------------------------------------------ */

  function sendMessage() {
    if (isWaiting) return;
    var text = inputEl.value.trim();
    if (!text) return;

    /* Ensure WS connected */
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      addMessageToUI(
        "bot",
        "Connecting... please wait a moment and try again."
      );
      if (!ws) connectWebSocket();
      return;
    }

    /* Save and display user message */
    var userMsg = { role: "user", content: text };
    messages.push(userMsg);
    saveMessages(messages);
    addMessageToUI("user", text);

    /* Build payload */
    var payload = { content: text };

    /* Send referrer URL as metadata on first message */
    if (!firstMessageSent) {
      firstMessageSent = true;
      payload.metadata = {
        referrer: document.referrer || "",
        page_url: window.location.href || "",
        user_agent: navigator.userAgent || "",
      };
    }

    ws.send(JSON.stringify(payload));

    /* Clear input and show typing */
    inputEl.value = "";
    inputEl.style.height = "auto";
    setInputDisabled(true);
    showTyping();
  }

  /* ------------------------------------------------------------------ */
  /*  Cleanup                                                            */
  /* ------------------------------------------------------------------ */

  function cleanup() {
    if (retryTimer) clearTimeout(retryTimer);
    if (ws) {
      ws.onclose = null; /* prevent reconnect */
      ws.close();
      ws = null;
    }
  }

  window.addEventListener("beforeunload", cleanup);

  /* ------------------------------------------------------------------ */
  /*  Initialization                                                     */
  /* ------------------------------------------------------------------ */

  function init() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", buildWidget);
    } else {
      buildWidget();
    }
  }

  init();
})();
