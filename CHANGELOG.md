# Journal des changements

## En cours (non publié)

- Intégration continue : `.github/workflows/tests.yml` installe le paquet
  (non éditable) et lance la suite sous Ubuntu (Python 3.10 à 3.14), macOS et
  Windows (Python 3.11 et 3.14).
- Nouveau test `tests/regression/test_table_ii_example.py` : la sortie
  `examples/table_ii.py --json` doit redonner la Table II à l'octet
  (flottants comparés par `float.hex`, seul `wall_seconds` exclu). Aucun
  changement des calculs.
- `.gitattributes` (`* text=auto eol=lf`, `*.npz binary`) : un clone Windows
  (`core.autocrlf=true`) réécrivait en CRLF `data/MANIFEST.json`, dont
  l'empreinte SHA-256 ne correspondait plus ; l'installation depuis un tel
  clone refusait alors tout calcul (`IntegrityError`, comportement voulu).
  Révélé par le premier passage de l'intégration continue. Les fichiers de
  PyPI (wheel et sdist, construits avec des fins de ligne LF) n'étaient pas
  touchés.

## 0.1.0 — 2026-11-24

- Première version préparée pour la publication : nom `certoutage`, banques
  embarquées et résultats de la Table II conservés à l'identique.
- README public en anglais, périmètre explicite et provenance chronologique
  distinguant l'archive ayant produit les résultats de cette extraction ultérieure.
- Métadonnées PEP 639, notices et répartition BSD-3-Clause AND MIT AND
  CC-BY-4.0 ; CITATION.cff et codemeta.json cohérents.
- Vocabulaire d'intégrité SHA-256 et fonction interne `verified_bytes` ; tests
  des versions et d'arrêt des calculs lors d'une divergence d'empreinte.
- Wheel et sdist destinés à une installation autonome, sans téléchargement
  de données à l'exécution. Aucun changement des calculs numériques.

## Corrections T28b — 24 novembre 2026 (0.1.0.dev1, non publiée)

- Validation exacte de `SNRGrid`, indépendante du contexte `decimal` ;
  affichage extérieur par quotient rationnel exact, sans arrondi intermédiaire.
- Contrôle de Laplace du générateur PPP rétabli aux trois points de l'archive,
  y compris pour la branche grossière ; erreurs explicites sous `python -O`.
- Neuf invariants des modules vendored `commun`, `ppp` et `thermal_backend`
  passent de `assert` à `ArithmeticError` ; calculs numériques conservés.
- Précision réelle des certificats fournis (160 bits), message `fresh` et
  contrat de la borne CDF stockée à B corrigés.
- Cible conservée dans `SNRDecision.target` ; différences de seuils refusées
  pour des cibles, usagers ou paramètres physiques incompatibles.
- Comportement `str()` de `np.float32(0.1)` figé par test et signalé au README.
  Tests d'audit, régressions binaires et installation propre vérifiés en T28b.

## 0.1.0.dev1 — 24 novembre 2026

Première phase locale, non publiée. API typée de modèle, coupure, plancher,
dimensionnement, comparateurs Gamma/moyenne/Eq. (3), borne J_max et Chernoff.
Banques v7 dont l'intégrité est vérifiée ; génération PPP locale pour une intensité nouvelle.
Régression brute des affirmations centrales, Table I, Figure 1 et Nakagami.
Exemples Table II et cas nouveau ; documentation du contrat et de ses limites.
