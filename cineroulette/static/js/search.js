(function () {
  const searchInput = document.getElementById("search-input");
  const grid = document.getElementById("dvd-grid");
  const filters = document.getElementById("filters");
  if (!grid) return;

  let debounceTimer = null;

  function currentParams() {
    const params = new URLSearchParams();
    if (searchInput && searchInput.value.trim()) {
      params.set("q", searchInput.value.trim());
    }
    const activeColor = filters ? filters.querySelector(".pastille-btn.active") : null;
    if (activeColor && activeColor.dataset.value) {
      params.set("couleur", activeColor.dataset.value);
    }
    const themeSelect = document.getElementById("theme-select");
    if (themeSelect && themeSelect.value) {
      params.set("theme", themeSelect.value);
    }
    return params;
  }

  function refresh() {
    const params = currentParams();
    fetch(`/dvd?${params.toString()}`, { headers: { "X-Requested-With": "fetch" } })
      .then((response) => response.text())
      .then((html) => {
        grid.innerHTML = html;
        const query = params.toString();
        history.replaceState(null, "", query ? `/dvd?${query}` : "/dvd");
      })
      .catch((err) => console.error("Erreur recherche DVD", err));
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(refresh, 300);
    });
  }

  if (filters) {
    filters.querySelectorAll(".pastille-btn, .chip-clear").forEach((btn) => {
      btn.addEventListener("click", () => {
        filters.querySelectorAll(".pastille-btn, .chip-clear").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        refresh();
      });
    });

    const themeSelect = document.getElementById("theme-select");
    if (themeSelect) {
      themeSelect.addEventListener("change", refresh);
    }
  }
})();
