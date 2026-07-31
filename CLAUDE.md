# Instructions pour Claude Code sur ce projet

## Règle d'or : isolation lors des tests

`DATABASE_URL` et `app.config["COVERS_DIR"]` sont **deux réglages indépendants**
(voir `cineroulette/config.py`) : surcharger l'un ne surcharge pas l'autre.

Avant tout script ou test qui touche la base ou les jaquettes, isoler **les
deux** :

```python
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_db_path}"
app.config["COVERS_DIR"] = tmp_covers_dir
```

Un oubli de `COVERS_DIR` écrase les vraies jaquettes de la collection
(`cineroulette/static/covers/`) — c'est arrivé deux fois pendant le
développement. Si un script n'a besoin que de piloter l'application (pas de
tester son code interne), préférer l'approche HTTP pure comme
`scripts/import_csv.py` : aucun accès direct à la base ou au disque, donc rien
à isoler.

## Avant de committer ou pusher

Ne jamais committer ou pusher sans confirmation explicite de l'utilisateur,
même après une série de changements validés individuellement.

## Cahier de tests

`CAHIER_DE_TESTS.md` est le plan de QA de référence — le mettre à jour après
tout changement fonctionnel (nouvelle route, comportement modifié). Il ne
stocke pas l'historique des exécutions : les résultats se communiquent en
chat, pas dans le fichier.
