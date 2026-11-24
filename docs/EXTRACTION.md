# Inventaire des extractions

Chaque ligne correspond à un fichier source. Les empreintes complètes et les destinations sont dans `EXTRACTION.json`. Les fichiers ci-dessous sont tous en lecture seule dans l’archive.

| Source dans archive v7 | Destination(s) dans le paquet | Transformation |
|---|---|---|
| `LICENSE` | `docs/ARCHIVE_LICENSE.txt` | copie identique |
| `LICENSES/CC-BY-4.0.txt` | `docs/CC-BY-4.0.txt` | copie identique |
| `banks_extra/C_N64.npz` | `src/certoutage/data/C_N64.npz` | copie identique |
| `banks_extra/C_N8.npz` | `src/certoutage/data/C_N8.npz` | copie identique |
| `banks_extra/GAMMA_l0p1_e3.npz` | `src/certoutage/data/GAMMA_l0p1_e3.npz` | copie identique |
| `banks_extra/GAMMA_l1p0_e3.npz` | `src/certoutage/data/GAMMA_l1p0_e3.npz` | copie identique |
| `banks_extra/GAMMA_l1p0_e4.npz` | `src/certoutage/data/GAMMA_l1p0_e4.npz` | copie identique |
| `banks_extra/PPP_l1p0_e3.npz` | `src/certoutage/data/PPP_l1p0_e3.npz` | copie identique |
| `banks_extra/PPP_l1p0_e4.npz` | `src/certoutage/data/PPP_l1p0_e4.npz` | copie identique |
| `banks_text/GAMMA_l0p1_e4/chi.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/GAMMA_l0p1_e4/clo.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/GAMMA_l0p1_e4/xhi.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/GAMMA_l0p1_e4/xlo.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e3/chi.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e3/clo.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e3/xhi.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e3/xlo.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e4/chi.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e4/clo.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e4/xhi.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/PPP_l0p1_e4/xlo.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_20/exact.csv` | `src/certoutage/data/SIG_20.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_20/gauss.csv` | `src/certoutage/data/SIG_20.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_20/levels.csv` | `src/certoutage/data/SIG_20.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_24/exact.csv` | `src/certoutage/data/SIG_24.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_24/gauss.csv` | `src/certoutage/data/SIG_24.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_24/levels.csv` | `src/certoutage/data/SIG_24.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_C_20/chernoff.csv` | `src/certoutage/data/SIG_C_20.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_C_20/levels.csv` | `src/certoutage/data/SIG_C_20.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_C_24/chernoff.csv` | `src/certoutage/data/SIG_C_24.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `banks_text/SIG_C_24/levels.csv` | `src/certoutage/data/SIG_C_24.npz` | reconditionnement NPZ sans perte, SHA des tableaux vérifié |
| `campaigns/t20/RESULTATS.csv` | `tests/regression/fixtures/nakagami.csv` | copie identique |
| `campaigns/t20/banques/SIG_m2_N12.npz` | `src/certoutage/data/SIG_m2_N12.npz` | copie identique |
| `campaigns/t20/banques/SIG_m2_N16.npz` | `src/certoutage/data/SIG_m2_N16.npz` | copie identique |
| `campaigns/t20/banques/SIG_m2_N20.npz` | `src/certoutage/data/SIG_m2_N20.npz` | copie identique |
| `campaigns/t20/banques/SIG_m2_N24.npz` | `src/certoutage/data/SIG_m2_N24.npz` | copie identique |
| `campaigns/t20/banques/SIG_m2_N32.npz` | `src/certoutage/data/SIG_m2_N32.npz` | copie identique |
| `campaigns/t20/banques/SIG_m2_N48.npz` | `src/certoutage/data/SIG_m2_N48.npz` | copie identique |
| `campaigns/t20/banques/SIG_m2_N64.npz` | `src/certoutage/data/SIG_m2_N64.npz` | copie identique |
| `campaigns/t20/banques/SIG_m2_N8.npz` | `src/certoutage/data/SIG_m2_N8.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N12.npz` | `src/certoutage/data/SIG_m3_N12.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N16.npz` | `src/certoutage/data/SIG_m3_N16.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N20.npz` | `src/certoutage/data/SIG_m3_N20.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N24.npz` | `src/certoutage/data/SIG_m3_N24.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N32.npz` | `src/certoutage/data/SIG_m3_N32.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N48.npz` | `src/certoutage/data/SIG_m3_N48.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N64.npz` | `src/certoutage/data/SIG_m3_N64.npz` | copie identique |
| `campaigns/t20/banques/SIG_m3_N8.npz` | `src/certoutage/data/SIG_m3_N8.npz` | copie identique |
| `campaigns/t20/banques/commun.npz` | `src/certoutage/data/commun.npz` | copie identique |
| `campaigns/t20/banques/m2_N8.npz` | `src/certoutage/data/m2_N8.npz` | copie identique |
| `campaigns/t20/banques/m3_N8.npz` | `src/certoutage/data/m3_N8.npz` | copie identique |
| `campaigns/t20/code/composer.py` | `src/certoutage/_runtime.py` | sélection de la grille units128 Nakagami |
| `campaigns/t23/banques/N64.npz` | `src/certoutage/data/m1_N64.npz` | copie identique |
| `campaigns/t23/banques/N8.npz` | `src/certoutage/data/m1_N8.npz` | copie identique |
| `campaigns/t23/banques/SIG_12.npz` | `src/certoutage/data/SIG_12.npz` | copie identique |
| `campaigns/t23/banques/SIG_16.npz` | `src/certoutage/data/SIG_16.npz` | copie identique |
| `campaigns/t23/banques/SIG_32.npz` | `src/certoutage/data/SIG_32.npz` | copie identique |
| `campaigns/t23/banques/SIG_48.npz` | `src/certoutage/data/SIG_48.npz` | copie identique |
| `campaigns/t23/banques/SIG_64.npz` | `src/certoutage/data/SIG_64.npz` | copie identique |
| `campaigns/t23/banques/SIG_8.npz` | `src/certoutage/data/SIG_8.npz` | copie identique |
| `campaigns/t24g_gamma/RESULTATS_gain_exact_gamma.json` | `tests/regression/fixtures/gamma.json` | copie identique |
| `expected/campaign_decisions/D1.json` | `tests/regression/fixtures/D1.json` | copie identique |
| `expected/campaign_decisions/D1_POINTS.csv` | `tests/regression/fixtures/D1_POINTS.csv` | copie identique |
| `expected/campaign_decisions/D2.json` | `tests/regression/fixtures/D2.json` | copie identique |
| `expected/campaign_decisions/D2_POINTS.csv` | `tests/regression/fixtures/D2_POINTS.csv` | copie identique |
| `expected/campaign_decisions/D3.json` | `tests/regression/fixtures/D3.json` | copie identique |
| `expected/campaign_decisions/D3_POINTS.csv` | `tests/regression/fixtures/D3_POINTS.csv` | copie identique |
| `expected/campaign_decisions/MINORANTS_N20.json` | `src/certoutage/data/MINORANTS_N20.json` ; `tests/regression/fixtures/MINORANTS_N20.json` | copie identique |
| `expected/campaign_decisions/MINORANTS_N24.json` | `src/certoutage/data/MINORANTS_N24.json` ; `tests/regression/fixtures/MINORANTS_N24.json` | copie identique |
| `nakagami/code/grouped.py` | `src/certoutage/_vendor/nak_grouped.py` | imports relatifs ; chargement remplacé par sous-classe dans _runtime.py |
| `nakagami/code/thermal.py` | `src/certoutage/_vendor/nak_thermal.py` ; `src/certoutage/_runtime.py` | imports relatifs ; chargement remplacé par sous-classe dans _runtime.py ; constructeur sans chdir ; rectangles et masses inchangés |
| `ppp/code/champ.py` | `src/certoutage/_generate.py` | fonction pure ; M paramétrable ; borne triviale si reste de Fourier >1 ; mêmes tableaux testés à M identique |
| `ppp/code/commun.py` | `src/certoutage/_vendor/commun.py` | imports relatifs ; contexte Arb géré par API |
| `ppp/code/minorants.py` | `src/certoutage/api.py` | J_max : distribution analytique et intégration pour nouveaux cas ; certificats centraux fournis |
| `ppp/code/oracles.py` | `src/certoutage/_vendor/oracles.py` ; `src/certoutage/_runtime.py` ; `src/certoutage/api.py` | imports relatifs ; constructeurs à chargement avec vérification d'intégrité ; méthodes numériques héritées sans modification ; dimensionnement avec grille paramétrable, comparaisons décimales exactes et nouveaux statuts publics |
| `ppp/code/ppp.py` | `src/certoutage/_vendor/ppp.py` | imports relatifs |
| `ppp/code/thermal_backend.py` | `src/certoutage/_vendor/thermal_backend.py` | imports relatifs ; contexte Arb géré par API |
| `tables/FIGURE_1.csv` | `tests/regression/fixtures/FIGURE_1.csv` | copie identique |
| `tables/TABLE_I_CERTIFICATS.csv` | `tests/regression/fixtures/TABLE_I_CERTIFICATS.csv` | copie identique |

Corrections T28b : les gardes vendored, le contrôle de Laplace et les
contrats de décisions ont ensuite été modifiés ; le détail et la preuve de
conservation figurent dans [LOGIC_CHANGES.md](LOGIC_CHANGES.md). Les empreintes
de destination dans `EXTRACTION.json` décrivent la version corrigée.

Préparation T28c (0.1.0) : vocabulaire de vérification d’intégrité harmonisé,
fonction interne renommée `verified_bytes`. Aucun calcul numérique changé.
Répartition des licences vérifiée dans l’archive : voir [LICENSES.md](../LICENSES.md).
Les empreintes de destination incluent ces modifications.
