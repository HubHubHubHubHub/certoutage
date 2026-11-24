# Régénérer les banques

Les consultations normales n'ont besoin ni du réseau ni de l'archive.
Les générateurs ci-dessous sont des outils locaux séparés ; ils ne publient
rien et ne soumettent aucun job. Le paquet livré conserve les banques
originales et leur manifeste. Une régénération ne remplace jamais ces
fichiers automatiquement.

## PPP et Gamma : générateur inclus

Depuis la racine du paquet :

```sh
python tools/regenerate_ppp.py --lam 0.2 --eta 3 --kind PPP --power 18 --output work/PPP_l0p2_e3.npz
python tools/regenerate_ppp.py --lam 0.2 --eta 3 --kind GAMMA --output work/GAMMA_l0p2_e3.npz
```

Pour les réglages historiques : `--power 20 --bits 160`. Les quatre tableaux
et leurs SHA-256 sont affichés. Le conteneur NPZ compressé peut avoir un
SHA différent sans changement de tableaux. La génération PPP/Gamma pour
λ=0,2, η=3, M=2^18 a été comparée à une copie du générateur original dont
seul M a changé : les huit tableaux ont les mêmes octets.

## Gain, thermique, Chernoff et J_max : copies de l'archive v7

L'archive doit être disponible localement. Installer `.[regenerate]` pour
SciPy, utilisé seulement par les générateurs historiques. `ARCHIVE` désigne
ici un chemin à remplacer explicitement ; aucune découverte réseau.

```sh
python tools/regenerate_from_archive.py --archive /chemin/archive_v7 --output work/rayleigh24 --kind signal --N 24
python tools/regenerate_from_archive.py --archive /chemin/archive_v7 --output work/chernoff24 --kind chernoff --N 24
python tools/regenerate_from_archive.py --archive /chemin/archive_v7 --output work/nakagami2_8 --kind nakagami --m 2 --N 8
python tools/regenerate_from_archive.py --archive /chemin/archive_v7 --output work/largest24 --kind largest --N 24
```

Chaque commande exige un nouveau répertoire hors archive. Elle copie les
sources nécessaires et consigne leurs empreintes dans `COPIES.json` avant
exécution. Seul l'accès obligatoire aux métadonnées du planificateur est
rendu facultatif (`os.environ.get` à la place de l'indexation). L'archive
reste en lecture seule. Les environnements historiques absolus et les
commandes de soumission ne sont pas utilisés.

`signal` recalcule la grille thermique commune, l'inversion d'amplitude
Rayleigh et la banque de signal. `chernoff` recalcule la grille commune,
l'amplitude et la banque Chernoff propagée. `nakagami` recalcule l'amplitude
et le signal par les sources T20, en réutilisant la banque thermique
commune fournie par l'archive. `largest` recalcule la distribution de
J_max et son intégration, mais réutilise la banque utile dont l'intégrité est vérifiée du
paquet et le tableau de planchers de référence de l'archive.

La banque commune peut aussi être recalculée séparément, dans le répertoire
copié, en exécutant `thermal_backend.common()` (ou `t4_backend.common()`
pour T20). Les banques d'amplitude Table I correspondent aux fichiers
`campaigns/t23/banques/N8.npz`, `N64.npz` et
`campaigns/t20/banques/m2_N8.npz`, `m3_N8.npz`. Les Chernoff Table I viennent
de `banks_extra/C_N8.npz` et `C_N64.npz` ; leur générateur spécifique est
`nakagami/code/chernoff_bank.py` (copier le dossier avant exécution).

La régénération complète N=24 n'a pas été exécutée pendant cette phase.
Il ne faut pas confondre un rejeu de consultation, le reconditionnement
sans perte d'une banque et sa construction à partir de zéro. Les valeurs
centrales de J_max sont les **certificats finaux** archivés, et non une
nouvelle banque de sa distribution reconstruite durant T28.

## Transport et intégrité

`data/MANIFEST.json` donne le SHA du fichier chargé, sa taille et les sources.
`docs/EXTRACTION.json` précise les opérations de copie/reconditionnement.
Les banques textuelles centrales sont vérifiées sur les octets CSV puis
sur les octets des tableaux, avant recompression sans perte en NPZ.

Pour une nouvelle version des banques, mettre à jour les données, leur
manifeste et son empreinte épinglée dans `_banks.py` après validation.
Ne pas seulement remplacer un fichier pour contourner `IntegrityError`.
Les tests de régression doivent ensuite décider explicitement si la
nouvelle version conserve les bornes brutes ou impose une version différente.
