# Changements de logique et preuves de conservation

L'archive v7 n'est pas modifiée. Les imports relatifs, les chemins et le
chargement ne suffisent pas à décrire toute l'extraction : les changements
suivants sont déclarés explicitement.

| Zone | Changement | Justification et vérification |
|---|---|---|
| `oracles.Environment.point`, `Signal.indices/lookup` | Corps numériques conservés par héritage | D1/D2/D3 : mêmes points bruts, mêmes décisions et mêmes différences ; Gamma : toutes les lignes centrales |
| Chargement des banques | Sources injectées en mémoire après SHA-256, plus de `chdir` ni de `ROOT/banques` dans le chemin actif | Reconditionnement CSV→NPZ contrôlé sur SHA de tableaux ; test négatif de corruption |
| Sélection d'environnement | Égalité décimale exacte avec 0,1/1 avant sélection de banque | Empêche une intensité nouvelle proche d'une intensité historique d'utiliser la mauvaise banque par arrondi du nom de fichier |
| Nakagami | Grille `units128` de T20, au lieu de supposer la grille Rayleigh | Vingt cas T20 reproduits, trois comparateurs quand évalués ; pas de prolongement interpolé de la CDF |
| Table I | Constructeur thermique sans fichiers relatifs ; sommes groupées historiques | Dix-huit requêtes aux endpoints des neuf cellules finies identiques ; cellule Eq. (3), N=8, 40 dB exclue |
| Génération PPP | `champ.py` devient une fonction sans écritures ; M paramétrable | Formules de restes recalculées avec le M réel. À λ=0,2, η=3, M=2^18 : tableaux PPP et Gamma bit-identiques à une copie du générateur original avec ce même M |
| Reste de Fourier trop grand | Si R>1, CDF grossière [0,1] et queue analytique à B, sans DFT | Inclusion triviale des probabilités ; protège le transport binaire64 pour λ extrêmement petit. Test λ=1e-500 ; aucune précision rare-événement revendiquée dans cette branche |
| Recherche du seuil | Grille passée par l'utilisateur ; censure gauche `feasible`, seuil [-∞, premier faisable] | Un point faisable suffit ; aucun endpoint exclu inventé. Test dédié ; conservation exacte des brackets historiques non censurés |
| Décision hors grille | `inconclusive`, même si tous les points finis testés sont exclus | Seul le plancher peut prouver l'impossibilité à tout SNR. Tests de grille épuisée et de plancher |
| Chernoff | Le plancher du majorant au-dessus de la cible donne `inconclusive`, jamais `excluded` pour l'outage | Reprend le sens correct du rejeu v7 ; conserve les valeurs et brackets de la règle suffisante |
| Contexte Arb | Plus de modification permanente de `ctx` à l'import ; précision/threads restaurés sous verrou | Test à contexte externe 80 bits, calcul à 192, retour à 80 ; banques explicitement maintenues à 160 bits |
| Affichage | Arrondis décimaux extérieurs, scale explicite ; quotient rationnel exact depuis T28b | Chaînes publiées des quatre affirmations centrales ; test supplémentaire au pas 1/128 dB |
| Diagnostics | `falsely feasible` / `masked` dérivés des statuts | Test Table II et conditions explicitement documentées ; aucun verdict physique induit par le seul comparateur |
| J_max | Certificats finaux centraux lus ; intégration pour les autres cas | Bornes centrales brutes identiques ; distribution analytique et enveloppes conservées pour le nouveau λ |

`_generate.py` conserve les formules des restes de l'archive. La partie
choix de grille, gestion de contexte, chargement et décision a changé :
la régression n'est donc pas présentée comme une extraction « interface
seulement ». Les preuves détaillées de T28 se trouvent dans `evidence/`
au niveau de la mission ; les tests livrés dans le paquet sont autonomes.

## Corrections T28b après audit Fable (24 novembre 2026)

| Constat | Modification | Conservation et test |
|---|---|---|
| M1 | Validation de `SNRGrid` par `Fraction`, puis recherche en unités entières de 1/128 dB | Aucun contexte décimal ne participe aux opérations ; bornes limitées à ±1000 dB et pas ≤2000, donc multiples binaires exactement représentables. Tests à précision 3, y compris avec pièges d'arrondi actifs, et contre-exemple 1,0001 rejeté |
| M2 | `Enclosure.format` divise exactement en rationnels et applique plancher/plafond aux unités décimales affichées | Pour q exact, floor(q·10^p)/10^p ≤ q ≤ ceil(q·10^p)/10^p. Aucun arrondi intermédiaire ; cas des échelles à 451 décimales, quotient à 500 chiffres et frontière exacte |
| M3 | Rétablissement du contrôle de Laplace de `ppp/code/champ.py:67–76`, omis lors de T28 ; exception `ArithmeticError` | Trois points s=0,1 ; 0,5 ; 1, mêmes masses et inégalités Arb que l'archive ; contrôle aussi de la branche R>1. Aucun tableau modifié. Tests des appels et injection d'une transformée incohérente |
| M4 | Remplacement de neuf `assert` par des gardes explicites dans trois fichiers vendored, détaillés ci-dessous | Conditions et opérations numériques conservées. Entrées fautives rejetées aussi sous `python -O` ; sorties de toutes les régressions comparées en binaire64 avant/après |
| M5 | Aucun changement de lecture des réels ; ajout d'un test et d'une phrase au README | `np.float32(0.1)` reste lu par `str()` et sélectionne la banque 0,1 ; le test passe déjà sur T28 |
| M6 | Message `fresh` mentionnant PPP et Gamma ; `provided-certificate.precision_bits=160` ; contrat de la CDF à B rectifié | Bornes inchangées ; le test λ=0,01 montre le dernier nœud plus lâche avec DFT. Cette dernière correction porte seulement sur le texte |
| M7 | Nouveau champ `SNRDecision.target` ; contrôle de cible/usager/convention/N/m/λ/η/R0 avant différence de seuils | Égalité décimale exacte ; comparateurs gain/interférence autorisés à différer. Les décisions exportées ont une métadonnée `target` supplémentaire ; bornes, statuts et diagnostics conservés |

Les changements vendored sont précisément :

- `_vendor/commun.py` : `out` vérifie la finitude et le transport extérieur ;
  `poisson_tail` vérifie n>κ (trois gardes).
- `_vendor/ppp.py` : `envelopes` vérifie L≤U et l'origine nulle, puis les
  masses positives ou nulles (deux gardes).
- `_vendor/thermal_backend.py` : `tighten` vérifie L≤U ; `outward` vérifie
  la finitude et le transport extérieur ; `gamma_series` vérifie x>0 et k>0
  (quatre gardes). Les quatre gardes analogues supplémentaires à celles
  citées dans M4 ont été converties pour conserver le même comportement
  de sûreté dans ces trois modules sous optimisation.

Le contrôle M3 est un filet de cohérence, pas une preuve indépendante :
pour exp(−sJ), fonction décroissante, les masses sur `xlo` majorent la
transformée, celles sur `xhi` la minorent ; la masse résiduelle à +∞
contribue zéro. On vérifie `lap_lo.lower() <= exact.upper()` et
`lap_hi.upper() >= exact.lower()`, comme l'archive, sans resserrer les CDF.

## English text throughout (26 November 2026, unreleased)

All user-facing text is now in English: exception messages, docstrings,
the `Contract.assumptions` strings, example output, and the comments and
docstrings of the tests. In `_vendor/`, only the nine exception messages
added in T28b and four comments or docstrings were translated. No
condition, operation or control flow changed. The one code-level edit
outside string literals is in `threshold_difference`, where the label
`"usager (user)"` became `name`.

Output changes are text only. `examples/table_ii.py --json` was compared
with the previous fixture value by value: same structure, same 30 binary64
values (`float.hex`), same integers, booleans and `None`. Exactly eight
distinct strings changed: the six assumptions and the two
"(raw probability)" annotations. The regression fixture
`tests/regression/fixtures/table_ii.json` was regenerated after this check.
The numbers in every other regression fixture are unchanged.

Les traces T28b dans `evidence/t28b/` au niveau de la mission conservent
les contre-tests sur l'ancien code, les empreintes des sorties avant/après,
les comparaisons des exemples aux JSON T28, et les durées des suites
normale et optimisée dans un environnement neuf. Les temps d'exécution
ne sont pas des sorties reproductibles ; l'ajout `target` est déclaré
et vérifié séparément lors de la comparaison des exports JSON.
