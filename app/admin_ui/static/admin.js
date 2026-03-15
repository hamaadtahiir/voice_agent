/* ============================================================
   Admin Panel – JavaScript Utilities
   ============================================================ */

(function () {
  "use strict";

  /* ----------------------------------------------------------
     Auth helpers
  ---------------------------------------------------------- */
  function getToken() {
    const match = document.cookie.match(/(^|;\s*)admin_token=([^;]*)/);
    return match ? decodeURIComponent(match[2]) : null;
  }

  function setToken(token) {
    document.cookie =
      "admin_token=" +
      encodeURIComponent(token) +
      "; path=/; max-age=86400; SameSite=Lax";
  }

  function clearToken() {
    document.cookie =
      "admin_token=; path=/; max-age=0; SameSite=Lax";
  }

  /* Attach JWT to every htmx request */
  document.addEventListener("htmx:configRequest", function (evt) {
    var token = getToken();
    if (token) {
      evt.detail.headers["Authorization"] = "Bearer " + token;
    }
  });

  /* Handle 401 responses globally */
  document.addEventListener("htmx:responseError", function (evt) {
    if (evt.detail.xhr && evt.detail.xhr.status === 401) {
      clearToken();
      window.location.href = "/admin/login";
    }
  });

  /* Authenticated fetch wrapper */
  window.authFetch = function (url, options) {
    options = options || {};
    options.headers = options.headers || {};
    var token = getToken();
    if (token) {
      options.headers["Authorization"] = "Bearer " + token;
    }
    if (
      options.body &&
      typeof options.body === "object" &&
      !(options.body instanceof FormData)
    ) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }
    return fetch(url, options).then(function (res) {
      if (res.status === 401) {
        clearToken();
        window.location.href = "/admin/login";
        return Promise.reject(new Error("Unauthorized"));
      }
      return res;
    });
  };

  /* ----------------------------------------------------------
     Toast notifications
  ---------------------------------------------------------- */
  window.showToast = function (message, type) {
    type = type || "success";
    var container = document.getElementById("toast-container");
    if (!container) return;

    var toast = document.createElement("div");
    toast.className = "toast toast-" + type;

    var icons = {
      success:
        '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
      error:
        '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
      info:
        '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z"/></svg>',
    };

    toast.innerHTML =
      (icons[type] || icons.info) +
      '<span class="flex-1">' +
      escapeHtml(message) +
      "</span>" +
      '<button onclick="this.parentElement.remove()" class="ml-2 opacity-60 hover:opacity-100">&times;</button>';

    container.appendChild(toast);
    setTimeout(function () {
      toast.classList.add("toast-exit");
      setTimeout(function () {
        toast.remove();
      }, 350);
    }, 4000);
  };

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  /* ----------------------------------------------------------
     Slug generator
  ---------------------------------------------------------- */
  window.generateSlug = function (text) {
    return text
      .toString()
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, "")
      .replace(/[\s_]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-+|-+$/g, "");
  };

  /* Auto-attach slug generation on business name input */
  document.addEventListener("DOMContentLoaded", function () {
    var nameInput = document.getElementById("business-name");
    var slugInput = document.getElementById("business-slug");
    if (nameInput && slugInput) {
      nameInput.addEventListener("input", function () {
        if (!slugInput.dataset.manual) {
          slugInput.value = generateSlug(nameInput.value);
        }
      });
      slugInput.addEventListener("input", function () {
        slugInput.dataset.manual = "1";
      });
    }
  });

  /* ----------------------------------------------------------
     Tab switching
  ---------------------------------------------------------- */
  window.switchTab = function (tabGroup, tabName) {
    /* Deactivate all buttons and panels in group */
    document
      .querySelectorAll('[data-tab-group="' + tabGroup + '"] .tab-btn')
      .forEach(function (btn) {
        btn.classList.remove("active");
      });
    document
      .querySelectorAll(
        '[data-tab-group="' + tabGroup + '"] .tab-panel'
      )
      .forEach(function (panel) {
        panel.classList.remove("active");
      });

    /* Also handle buttons outside wrapper */
    document
      .querySelectorAll(
        '.tab-btn[data-tab-target="' + tabName + '"][data-group="' + tabGroup + '"]'
      )
      .forEach(function (btn) {
        btn.classList.add("active");
      });

    /* Activate selected */
    var activeBtn = document.querySelector(
      '.tab-btn[data-tab-target="' + tabName + '"]'
    );
    if (activeBtn) activeBtn.classList.add("active");

    var activePanel = document.getElementById("tab-" + tabName);
    if (activePanel) activePanel.classList.add("active");
  };

  /* ----------------------------------------------------------
     Chart helpers
  ---------------------------------------------------------- */
  window.chartColors = {
    blue: "rgba(37, 99, 235, 1)",
    blueBg: "rgba(37, 99, 235, 0.15)",
    green: "rgba(22, 163, 74, 1)",
    greenBg: "rgba(22, 163, 74, 0.15)",
    red: "rgba(220, 38, 38, 1)",
    redBg: "rgba(220, 38, 38, 0.15)",
    yellow: "rgba(202, 138, 4, 1)",
    yellowBg: "rgba(202, 138, 4, 0.15)",
    purple: "rgba(147, 51, 234, 1)",
    purpleBg: "rgba(147, 51, 234, 0.15)",
    slate: "rgba(100, 116, 139, 1)",
    slateBg: "rgba(100, 116, 139, 0.15)",
  };

  window.defaultChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { usePointStyle: true, padding: 16 } },
    },
  };

  window.createPieChart = function (canvasId, labels, data, colors) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [
          {
            data: data,
            backgroundColor: colors || [
              chartColors.blue,
              chartColors.green,
              chartColors.yellow,
              chartColors.red,
              chartColors.purple,
              chartColors.slate,
            ],
            borderWidth: 0,
          },
        ],
      },
      options: Object.assign({}, defaultChartOptions, {
        cutout: "60%",
      }),
    });
  };

  window.createBarChart = function (canvasId, labels, data, color) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Leads",
            data: data,
            backgroundColor: color || chartColors.blue,
            borderRadius: 4,
            barThickness: 32,
          },
        ],
      },
      options: Object.assign({}, defaultChartOptions, {
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 } },
          x: { grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      }),
    });
  };

  window.createLineChart = function (canvasId, labels, data, color) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Leads",
            data: data,
            borderColor: color || chartColors.blue,
            backgroundColor: (color || chartColors.blueBg),
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
        ],
      },
      options: Object.assign({}, defaultChartOptions, {
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 } },
          x: { grid: { display: false } },
        },
      }),
    });
  };

  /* ----------------------------------------------------------
     Logout
  ---------------------------------------------------------- */
  window.logout = function () {
    clearToken();
    window.location.href = "/admin/login";
  };

  /* ----------------------------------------------------------
     Date / time formatting
  ---------------------------------------------------------- */
  window.formatDate = function (iso) {
    if (!iso) return "N/A";
    var d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  window.formatTime = function (iso) {
    if (!iso) return "";
    var d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
    });
  };

  window.formatDateTime = function (iso) {
    if (!iso) return "N/A";
    return formatDate(iso) + " " + formatTime(iso);
  };

  window.relativeTime = function (iso) {
    if (!iso) return "";
    var now = Date.now();
    var then = new Date(iso).getTime();
    var diff = Math.floor((now - then) / 1000);
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.floor(diff / 60) + "m ago";
    if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
    if (diff < 604800) return Math.floor(diff / 86400) + "d ago";
    return formatDate(iso);
  };

  /* ----------------------------------------------------------
     Score helpers
  ---------------------------------------------------------- */
  window.scoreClass = function (score) {
    if (score == null) return "";
    if (score < 30) return "score-low";
    if (score <= 60) return "score-mid";
    return "score-high";
  };

  window.scoreBgClass = function (score) {
    if (score == null) return "";
    if (score < 30) return "score-bg-low";
    if (score <= 60) return "score-bg-mid";
    return "score-bg-high";
  };

  /* ----------------------------------------------------------
     Mobile sidebar toggle
  ---------------------------------------------------------- */
  window.toggleSidebar = function () {
    var sidebar = document.getElementById("sidebar");
    var overlay = document.getElementById("sidebar-overlay");
    if (sidebar) sidebar.classList.toggle("open");
    if (overlay) overlay.classList.toggle("open");
  };

  /* ----------------------------------------------------------
     Dashboard auto-refresh
  ---------------------------------------------------------- */
  var dashboardInterval = null;

  window.startDashboardRefresh = function (loadFn, intervalMs) {
    stopDashboardRefresh();
    dashboardInterval = setInterval(loadFn, intervalMs || 30000);
  };

  window.stopDashboardRefresh = function () {
    if (dashboardInterval) {
      clearInterval(dashboardInterval);
      dashboardInterval = null;
    }
  };

  /* Clean up interval when navigating away */
  window.addEventListener("beforeunload", stopDashboardRefresh);

  /* ----------------------------------------------------------
     On page load – redirect to login if no token (except login page)
  ---------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    var isLoginPage =
      window.location.pathname === "/admin/login" ||
      window.location.pathname === "/admin/login/";
    if (!isLoginPage && !getToken()) {
      window.location.href = "/admin/login";
    }
  });
})();
