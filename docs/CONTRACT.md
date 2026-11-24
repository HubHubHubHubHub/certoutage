# Contrat de certification

## Objet mathématique

Avec V_k=sqrt(E_k F_k), A_N=Σ V_k et W=A_N²(10+Z)²/101, les deux quantités
sont P_INR(ρ)=E F_W(d_i(1+J)/ρ) et P_TX(ρ)=E F_W(d_i(J+1/ρ)).
Toutes les indépendances du modèle de la Letter sont nécessaires. Les
résultats des deux usagers sont marginaux ; aucune probabilité conjointe
ni allocation optimale d'une surface partagée n'est certifiée.

L'inversion de la transformée du gain, les restes et les rectangles
thermiques proviennent de l'archive. Les banques utiles sont fournies à
160 bits. Les rectangles couvrent [-12,12], avec -10 et 0 aux frontières ;
la masse omise est majorée par 2φ(12)/12. Le zéro du facteur thermique
n'est ni supprimé ni traité comme une probabilité ponctuelle positive.

## Composition des distributions

Pour une CDF encadrée aux nœuds x_j par L_j et U_j, deux distributions
discrètes ordonnées stochastiquement sont construites. Les masses sont les
différences d'UNE même enveloppe cumulative ; elles ne sont pas remplacées
par des intervalles de masses indépendants. Le résidu inférieur est placé
au dernier nœud fini, le supérieur à +∞. Pour tout test croissant g :
E g(X-) ≤ E g(J) ≤ E g(X+).

L'API hérite sans changement des méthodes `Signal.indices`, `Signal.lookup`
et `Environment.point` de `ppp/code/oracles.py`. Les recherches de nœuds sont
conservatrices, les additions et produits binaires64 sont élargis par
`nextafter`, et les masses et produits scalaires restent dans Arb. Aucune
interpolation linéaire ni renormalisation de queue n'est utilisée.

Les paramètres NOMA et thermiques sont fixés. Un nouveau λ ne justifie
pas de changer la banque de gain ; il change la distribution PPP, qui est
recalculée avec les restes suivants.

## Inversion PPP à la demande

Pour η=3 ou 4, on utilise les expressions explicites de l'archive pour
L_J(s)=exp(-2πλ ∫_1^∞ sr/(r^η+s) dr), avec branches principales.
Soient α=2/η, β=π²λα/[2 sin(πα/2)], B=128, cB=20, K=M/2 et
ξ=β(2πK/B)^α. Le reste de Fourier est

R=exp(πλ-ξ)/π × (1/(2K)+1/(αξ)).

Avec τ=exp(-B/2+2πλ/(η-2)) et a0=1/expm1(20), le certificat aux nœuds est
S_M-a0-exp(cx)R ≤ F_J(x) ≤ S_M-a0+exp(cx)R+τa0.
F_J(0)=0. Dans la branche DFT, l'encadrement **stocké** à B est
F_J(B)∈[L_{M−1},1], où L est l'enveloppe inférieure resserrée sur les
nœuds uniformes jB/M : l'indice inférieur conservateur à B vaut M−1.
La borne analytique max(0,1−τ) est appliquée au nœud uniforme M, mais
n'est pas reportée dans `clo[-1]` après cette sélection d'indice.
Dans la branche R>1 sans DFT, l'encadrement stocké à B est bien
[max(0,1−τ),1], avec transport binaire64 vers l'extérieur. Ces choix
peuvent donner une borne stockée à B plus faible lorsque M augmente.
Les constantes, DFT et restes sont
calculés dans Arb/Acb. Les nœuds de composition sont ceux de l'archive,
x_j=10^(j/2560)-1, puis B ; leurs abscisses sont encadrées.

Le changement M=2^20 vers M configurable conserve cette preuve : ξ, K et
l'exponentielle de discrétisation utilisent le M effectif. Il ne conserve
pas nécessairement la largeur des certificats. Si R>1, le calcul retourne
les bornes de CDF [0,1], avec la borne analytique de queue au dernier nœud,
sans entreprendre une DFT inutile. C'est un certificat grossier explicite,
pas une extrapolation vers un cas mieux conditionné.

Après génération PPP, les enveloppes discrètes sont contrôlées contre
L_J(s) aux trois valeurs s=0,1 ; 0,5 ; 1, comme dans `champ.py` de
l'archive. Une incohérence lève `ArithmeticError`, même sous `python -O`.
Ce contrôle de cohérence ne remplace pas les bornes analytiques.

La branche Gamma utilise la CDF Gamma régulière dans Arb et, si nécessaire,
une série positive avec reste géométrique ou une borne exponentielle. Ses
moments sont ceux de J. Cette intégration rigoureuse ne borne pas le biais
de substitution PPP → Gamma.

## Contrats particuliers

La distribution du plus grand interférent est
P(J_max≥x)=1-exp(-Λ(x)), Λ(x)=(2πλ/η)x^(-2/η)Γ(2/η,x), R0=1.
Puisque J_max≤J, E F_W(d_i J_max) est une **floor lower bound**. L'intervalle
retourné encadre cette borne inférieure ; son bord supérieur n'est pas une
borne supérieure du plancher PPP. Les valeurs centrales archivées sont
étiquetées `provided-certificate`.
Leur `precision_bits` reste 160, même si une précision supérieure a été
demandée : aucune nouvelle intégration n'est effectuée dans cette branche.

Le comparateur Chernoff est C_N(a)=inf_{s≥0} exp(sa)L(s)^N. Les banques
encadrent le comparateur propagé dans les mêmes intégrations. La racine
d'optimisation a été certifiée par signes ; la singularité amovible près
de s=2 utilise une série avec reste établi. Les lower endpoints du
comparateur ne sont pas des lower endpoints de la coupure. L'API garantit
qu'ils ne produisent pas `excluded` pour le modèle physique.

La récurrence de la transformée Nakagami dans l'archive utilise l'indice
entier 2m-1 et une borne de variation explicite. Elle n'est pas une routine
certifiée pour m réel arbitraire. Pour m=2,3 on réutilise les banques et
leurs bornes ; la génération et la stabilité pour d'autres m ne sont pas
revendiquées.

## Ce qui est une preuve et ce qui ne l'est pas

La validité mathématique est conditionnelle aux preuves analytiques
référencées dans la Letter et `notes/decisions/` de l'archive, à la validité
d'Arb/Acb et au respect de l'arithmétique IEEE requise. La mission extrait
et teste ce contrat ; elle ne constitue pas une preuve formelle du moteur
ni une nouvelle démonstration indépendante de toutes les bornes de l'article.

Un SHA-256 vérifie l'intégrité des données par rapport à une empreinte de
référence ; il ne prouve ni leur provenance ni leur justesse. Une régression brute
atteste la conservation des calculs testés. Le recoupement à 192 bits et
DFT doublée du cas nouveau apporte une vérification supplémentaire, avec
la même banque utile à 160 bits ; il n'est pas une preuve indépendante.
