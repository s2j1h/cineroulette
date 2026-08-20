(function () {
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function buildHtml(providers) {
    if (!providers.length) {
      return `<p class="streaming-label streaming-none">📺 Pas disponible en streaming (abonnement)</p>`;
    }
    const logos = providers
      .map((p) => {
        const name = escapeHtml(p.name);
        return p.logo_url
          ? `<img class="streaming-logo" src="${p.logo_url}" alt="${name}" title="${name}" loading="lazy">`
          : `<span class="streaming-name">${name}</span>`;
      })
      .join("");
    return `
      <p class="streaming-label">📺 En streaming (abonnement)</p>
      <div class="streaming-logos">${logos}</div>
    `;
  }

  // Remplit `container` avec les plateformes du film. Sans tmdbId (film non lié à
  // TMDB), on n'affiche rien : l'absence de disponibilité est inconnue, pas nulle.
  function render(container, tmdbId) {
    if (!container) return;
    if (!tmdbId) {
      container.innerHTML = "";
      return;
    }
    container.innerHTML = `<p class="streaming-label streaming-loading">Recherche des plateformes…</p>`;
    fetch(`/streaming/${tmdbId}`)
      .then((response) => (response.ok ? response.json() : { providers: [] }))
      .then((data) => {
        container.innerHTML = buildHtml(data.providers || []);
      })
      .catch((err) => {
        console.error("Erreur récupération streaming", err);
        container.innerHTML = "";
      });
  }

  window.CineStreaming = { render };

  // Auto-remplissage des conteneurs statiques (fiche détail) au chargement.
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-streaming-tmdb]").forEach((el) => {
      const raw = el.getAttribute("data-streaming-tmdb");
      render(el, raw ? parseInt(raw, 10) : null);
    });
  });
})();
