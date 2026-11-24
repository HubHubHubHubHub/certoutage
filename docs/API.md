# API publique

Toutes les entrées publiques sont annotées. Les objets sont des dataclasses
immuables ; `dataclasses.asdict` permet leur export JSON (remplacer ±∞ par
une représentation textuelle pour du JSON strict en cas de censure).

## Modèle et calcul

`Model(N=24, lam="0.1", eta=4, convention="C-TX", m=1, R0=1)` valide le
périmètre documenté dans Scope. Les paramètres réels sont lus par leur
représentation décimale : utiliser des chaînes pour préciser un nombre
décimal intentionnel. Les booléens, NaN, infinis et cas non couverts sont
rejetés. Le paramètre `m` décrit les deux puissances élémentaires, pas une
approximation Gamma du gain total.

`Numerics(precision_bits=160, ppp_dft_power=18, bank_policy="auto")` contrôle
les calculs courants. `bank_policy="fresh"` régénère la distribution PPP ou
Gamma ; la banque de signal reste fournie. 160 à 1024 bits et M de 2^12 à
2^20 sont acceptés. Une grille insuffisante élargit les intervalles. Les
choix supérieurs consomment davantage de mémoire et de temps.

`outage_enclosure(model, user, snr_db, *, gain="exact", interference="PPP",
numerics=Numerics())` renvoie `Enclosure(lower, upper, contract)`. Le SNR est
fini, en dB, dans [-1000,1000]. `floor` a les mêmes paramètres sauf `snr_db`.
L'absence de PPP s'obtient par `lam=0` ou `interference="none"`.

Les options `gain` sont `exact`, `eq3`, `chernoff` ; `interference` vaut
`PPP`, `Gamma`, `mean` ou `none`. Le nom public `eq3` évite d'utiliser
« gauss » sans préciser le comparateur. Les identifiants historiques
internes `gauss` et `GAMMA` n'apparaissent pas comme noms de méthodes publiques.

`Enclosure.as_dict()` restitue les floats bruts. `format(scale="1e-5",
places=4)` divise l'intervalle par l'échelle et arrondit **vers l'extérieur**
par quotient rationnel exact des bornes binaires64 et de l'échelle décimale,
puis plancher/plafond entiers, indépendamment du contexte `decimal`.
Dans la Table II, Eq. (3) + Gamma est affiché à trois décimales, les deux
premières lignes à quatre, conformément au manuscrit.

## Dimensionnement

`required_snr(model, user, target, grid=SNRGrid(), *, gain="exact",
interference="PPP", numerics=Numerics())` accepte 0 < target < 1.
`SNRGrid(start=-40, stop=96, step="0.0625")` est explicite ; tous ses
paramètres sont des multiples de 1/128 dB et stop-start un multiple du pas.
La validation est rationnelle exacte ; les valeurs stockées en binaire64
sont représentables exactement et servent directement à la recherche.

Le résultat `SNRDecision` contient :

- `status` : `feasible`, `excluded`, `inconclusive` ;
- `lower_db`, `upper_db` : encadrement du seuil si faisable ; -∞ à gauche
  si le début de grille est déjà faisable, aucun bord fini inventé ;
- `floor` : certificat de plancher ;
- `reason` : seuil fini, censure, grille épuisée ou plancher indécidé ;
- `undecided_points` : nombre de points entre les deux frontières finies ;
- `scope` et `contract` : objet de la décision et provenance des requêtes
  finies, même lorsque le plancher analytique C-INR n'utilise aucune banque.
- `target` : cible décimale de la décision, conservée aussi pour les
  exclusions, les recherches inconclusives et la ligne J_max.

La recherche binaire conserve les bornes par monotonie de la coupure et
revérifie les deux points finaux. Une borne basse strictement au-dessus de
la cible est nécessaire pour exclure. Une borne haute ≤ cible suffit pour
certifier un point. Des valeurs de cible égales à un endpoint sont comparées
exactement en décimal à la valeur binaire du float, sans tolérance numérique.

Pour `gain="chernoff"`, le seuil est celui de la **règle suffisante de
Chernoff**, et non un encadrement du seuil optimal de coupure. La borne
inférieure du comparateur ne permet pas d'exclure le modèle physique : le
statut reste `inconclusive` quand son plancher dépasse la cible.

`threshold_difference(a,b)` exige deux seuils faisables finis non censurés,
de même cible, même usager et mêmes N, m, λ, η, R0 et convention.
Les écritures décimales équivalentes sont acceptées ; le gain et le modèle
d'interférence peuvent différer pour comparer les approximations.
Une cible ou un paramètre de comparaison absent, notamment dans une décision
construite à la main, est refusé avec `ValueError`.
La fonction soustrait directement `[a.lower-b.upper, a.upper-b.lower]`. Pour l'erreur
totale, comparer directement Eq. (3) + moyenne à exact + PPP ; ne pas
additionner les deux intervalles qui contiennent un seuil partagé.

## Comparaisons

`compare_approximations` renvoie six `ComparisonRow`. Chaque ligne contient
son certificat de plancher, sa décision et éventuellement `diagnostic`.

`falsely feasible` exige une exclusion PPP prouvée et un SNR fini faisable
pour l'approximation. `masked` exige que l'exact + Gamma (ou moyenne) soit
falsely feasible et que le remplacement du gain par Eq. (3) exclue cette
approximation. Le diagnostic ne change pas la quantité certifiée.

`largest_interferer_bound(model,user)` encadre la borne inférieure du
plancher TX. Pour C-INR, le plancher correspondant est exactement zéro.
Les cas centraux N=20/24, Rayleigh, λ=0,1 ou 1, η=4, usager 1 chargent leurs
certificats finaux. Les autres cas composent à la demande la distribution
analytique de J_max avec la banque utile.
Un certificat fourni indique toujours `precision_bits=160`, sans nouvelle
intégration, quelle que soit la précision demandée dans `numerics`.

## Intégrité et concurrence

Une incohérence de SHA-256 lève `IntegrityError` avant `numpy.load`.
`allow_pickle=False` est imposé. `clear_cache()` libère les objets de calcul
et force la vérification lors des lectures suivantes. Modifier une banque
sur disque ne change pas rétroactivement les tableaux déjà chargés.

Le contexte global Arb est restauré après chaque appel, y compris en cas
d'exception. Les appels de ce paquet sont sérialisés par verrou. Un autre
logiciel modifiant `flint.ctx` en parallèle ne participe pas à ce verrou :
utiliser des processus séparés dans cette situation. Aucun parallélisme de
cluster n'est requis ni déclenché.
