(function () {
  const root = document.documentElement;
  const STORAGE_KEY = 'wisebudTheme';

  function getCurrent() {
    return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function setTheme(theme) {
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (_) {}
    updateToggleIcon();
  }

  function updateToggleIcon() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    const isDark = getCurrent() === 'dark';
    btn.setAttribute('data-mode', isDark ? 'dark' : 'light');
    btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    btn.title = btn.getAttribute('aria-label');
  }

  // Initialize from storage or media query
  (function init() {
    let saved;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch (_) {}
    if (saved === 'dark' || saved === 'light') {
      setTheme(saved);
    } else {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      setTheme(prefersDark ? 'dark' : 'light');
    }
  })();

  document.addEventListener('click', (e) => {
    const toggle = e.target.closest('#theme-toggle');
    if (!toggle) return;
    const next = getCurrent() === 'dark' ? 'light' : 'dark';
    setTheme(next);
  });

  document.addEventListener('DOMContentLoaded', updateToggleIcon);
})();


