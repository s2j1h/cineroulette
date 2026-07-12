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
    const activeTheme = filters ? filters.querySelector(".hashtag-btn.active") : null;
    if (activeTheme && activeTheme.dataset.value) {
      params.set("theme", activeTheme.dataset.value);
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
    filters.querySelectorAll(".filter-group").forEach((group) => {
      group.querySelectorAll(".pastille-btn, .hashtag-btn, .chip-clear").forEach((btn) => {
        btn.addEventListener("click", () => {
          group.querySelectorAll(".pastille-btn, .hashtag-btn, .chip-clear").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          refresh();
        });
      });
    });
  }
})();
