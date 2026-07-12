(function () {
  const resultEl = document.getElementById("roulette-result");
  const messageEl = document.getElementById("roulette-message");
  const btnRandom = document.getElementById("btn-random");
  const btnColor = document.getElementById("btn-same-color");
  const btnTheme = document.getElementById("btn-same-theme");

  const COULEUR_HEX = { rouge: "#c0392b", bleu: "#2765ff", "dorée": "#caa63d", argent: "#9aa0a6" };

  let current = null;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function renderFilm(dvd) {
    current = dvd;
    messageEl.hidden = true;
    resultEl.classList.remove("empty");

    const coverHtml = dvd.jaquette_url
      ? `<img src="${dvd.jaquette_url}" alt="Jaquette de ${escapeHtml(dvd.titre_fr)}">`
      : `<div class="cover-placeholder">🎞️</div>`;

    resultEl.innerHTML = `
      <div class="roulette-card">
        ${coverHtml}
        <div class="roulette-card-info">
          <span class="pastille" style="--pastille-color: ${COULEUR_HEX[dvd.couleur] || "#888"};" title="${escapeHtml(dvd.couleur)}"></span>
          <h2>${escapeHtml(dvd.titre_fr)}</h2>
          ${dvd.titre_en && dvd.titre_en !== dvd.titre_fr ? `<p class="subtitle">${escapeHtml(dvd.titre_en)}</p>` : ""}
          <p class="tags">
            ${dvd.annee ? `<span class="tag">${escapeHtml(dvd.annee)}</span>` : ""}
            ${dvd.theme ? `<span class="tag">${escapeHtml(dvd.theme)}</span>` : ""}
            ${dvd.note_imdb ? `<span class="tag">⭐ ${escapeHtml(dvd.note_imdb)}/10</span>` : ""}
          </p>
          ${dvd.resume ? `<p class="resume">${escapeHtml(dvd.resume)}</p>` : ""}
          <p><a href="/dvd/${dvd.id}">Voir la fiche complète →</a></p>
        </div>
      </div>
    `;

    btnColor.hidden = false;
    btnTheme.hidden = false;
    btnTheme.disabled = !dvd.theme;
  }

  function draw(params) {
    fetch(`/random?${params.toString()}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          messageEl.textContent = data.message;
          messageEl.hidden = false;
          return;
        }
        renderFilm(data);
      })
      .catch((err) => {
        console.error("Erreur tirage roulette", err);
        messageEl.textContent = "Erreur lors du tirage, réessayez.";
        messageEl.hidden = false;
      });
  }

  btnRandom.addEventListener("click", () => {
    const params = new URLSearchParams();
    if (current) params.set("exclude", current.id);
    draw(params);
  });

  btnColor.addEventListener("click", () => {
    if (!current) return;
    const params = new URLSearchParams();
    params.set("couleur", current.couleur);
    params.set("exclude", current.id);
    draw(params);
  });

  btnTheme.addEventListener("click", () => {
    if (!current || !current.theme) return;
    const params = new URLSearchParams();
    params.set("theme", current.theme);
    params.set("exclude", current.id);
    draw(params);
  });
})();
