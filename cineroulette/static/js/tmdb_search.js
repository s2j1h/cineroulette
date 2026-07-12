(function () {
  const queryInput = document.getElementById("tmdb-query");
  const resultsEl = document.getElementById("tmdb-results");
  if (!queryInput || !resultsEl) return;

  const form = queryInput.closest("form");
  let debounceTimer = null;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function search() {
    const q = queryInput.value.trim();
    if (!q) {
      resultsEl.innerHTML = "";
      return;
    }
    fetch(`/dvd/tmdb_search?q=${encodeURIComponent(q)}`)
      .then((r) => r.json())
      .then((candidates) => {
        if (!candidates.length) {
          resultsEl.innerHTML = '<p class="empty-state">Aucun résultat TMDB.</p>';
          return;
        }
        resultsEl.innerHTML = candidates
          .map(
            (c) => `
          <div class="tmdb-candidate" data-id="${c.id}">
            ${c.poster_url ? `<img src="${c.poster_url}" alt="">` : ""}
            <p>${escapeHtml(c.titre_fr)} ${c.annee ? `(${escapeHtml(c.annee)})` : ""}</p>
          </div>
        `
          )
          .join("");

        resultsEl.querySelectorAll(".tmdb-candidate").forEach((card) => {
          card.addEventListener("click", () => pick(card));
        });
      })
      .catch((err) => console.error("Erreur recherche TMDB", err));
  }

  function pick(card) {
    fetch(`/dvd/tmdb_pick?movie_id=${card.dataset.id}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          console.error(data.error);
          return;
        }
        resultsEl.querySelectorAll(".tmdb-candidate").forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected");
        fillForm(data);
      })
      .catch((err) => console.error("Erreur sélection TMDB", err));
  }

  function fillForm(data) {
    const fields = {
      titre_fr: data.titre_fr,
      titre_en: data.titre_en,
      resume: data.resume,
      theme: data.theme,
      annee: data.annee,
      note_imdb: data.note_imdb,
    };
    Object.keys(fields).forEach((name) => {
      const el = form.querySelector(`[name="${name}"]`);
      if (el && fields[name] !== null && fields[name] !== undefined) {
        el.value = fields[name];
      }
    });
    const urlField = form.querySelector('[name="jaquette_url"]');
    if (urlField && data.jaquette_url) urlField.value = data.jaquette_url;

    const tmdbIdField = form.querySelector('[name="tmdb_id"]');
    if (tmdbIdField && data.tmdb_id) tmdbIdField.value = data.tmdb_id;
  }

  queryInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(search, 350);
  });

  // Pré-rempli (ex: depuis le scan) : lance la recherche tout de suite, sans
  // attendre une saisie, pour afficher les candidats sans action de l'utilisateur.
  if (queryInput.value.trim()) {
    search();
  }
})();
