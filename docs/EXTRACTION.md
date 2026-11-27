# Extraction inventory

Each row is one source file. The full digests and destinations are in `EXTRACTION.json`. All the files below are read-only in the archive.

| Source in archive v7 | Destination(s) in the package | Transformation |
|---|---|---|
| `LICENSE` | `docs/ARCHIVE_LICENSE.txt` | identical copy |
| `LICENSES/CC-BY-4.0.txt` | `docs/CC-BY-4.0.txt` | identical copy |
| `banks_extra/C_N64.npz` | `src/certoutage/data/C_N64.npz` | identical copy |
| `banks_extra/C_N8.npz` | `src/certoutage/data/C_N8.npz` | identical copy |
| `banks_extra/GAMMA_l0p1_e3.npz` | `src/certoutage/data/GAMMA_l0p1_e3.npz` | identical copy |
| `banks_extra/GAMMA_l1p0_e3.npz` | `src/certoutage/data/GAMMA_l1p0_e3.npz` | identical copy |
| `banks_extra/GAMMA_l1p0_e4.npz` | `src/certoutage/data/GAMMA_l1p0_e4.npz` | identical copy |
| `banks_extra/PPP_l1p0_e3.npz` | `src/certoutage/data/PPP_l1p0_e3.npz` | identical copy |
| `banks_extra/PPP_l1p0_e4.npz` | `src/certoutage/data/PPP_l1p0_e4.npz` | identical copy |
| `banks_text/GAMMA_l0p1_e4/chi.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/GAMMA_l0p1_e4/clo.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/GAMMA_l0p1_e4/xhi.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/GAMMA_l0p1_e4/xlo.csv` | `src/certoutage/data/GAMMA_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e3/chi.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e3/clo.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e3/xhi.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e3/xlo.csv` | `src/certoutage/data/PPP_l0p1_e3.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e4/chi.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e4/clo.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e4/xhi.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/PPP_l0p1_e4/xlo.csv` | `src/certoutage/data/PPP_l0p1_e4.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_20/exact.csv` | `src/certoutage/data/SIG_20.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_20/gauss.csv` | `src/certoutage/data/SIG_20.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_20/levels.csv` | `src/certoutage/data/SIG_20.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_24/exact.csv` | `src/certoutage/data/SIG_24.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_24/gauss.csv` | `src/certoutage/data/SIG_24.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_24/levels.csv` | `src/certoutage/data/SIG_24.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_C_20/chernoff.csv` | `src/certoutage/data/SIG_C_20.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_C_20/levels.csv` | `src/certoutage/data/SIG_C_20.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_C_24/chernoff.csv` | `src/certoutage/data/SIG_C_24.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `banks_text/SIG_C_24/levels.csv` | `src/certoutage/data/SIG_C_24.npz` | lossless NPZ repackaging, array SHA-256 checked |
| `campaigns/t20/RESULTATS.csv` | `tests/regression/fixtures/nakagami.csv` | identical copy |
| `campaigns/t20/banques/SIG_m2_N12.npz` | `src/certoutage/data/SIG_m2_N12.npz` | identical copy |
| `campaigns/t20/banques/SIG_m2_N16.npz` | `src/certoutage/data/SIG_m2_N16.npz` | identical copy |
| `campaigns/t20/banques/SIG_m2_N20.npz` | `src/certoutage/data/SIG_m2_N20.npz` | identical copy |
| `campaigns/t20/banques/SIG_m2_N24.npz` | `src/certoutage/data/SIG_m2_N24.npz` | identical copy |
| `campaigns/t20/banques/SIG_m2_N32.npz` | `src/certoutage/data/SIG_m2_N32.npz` | identical copy |
| `campaigns/t20/banques/SIG_m2_N48.npz` | `src/certoutage/data/SIG_m2_N48.npz` | identical copy |
| `campaigns/t20/banques/SIG_m2_N64.npz` | `src/certoutage/data/SIG_m2_N64.npz` | identical copy |
| `campaigns/t20/banques/SIG_m2_N8.npz` | `src/certoutage/data/SIG_m2_N8.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N12.npz` | `src/certoutage/data/SIG_m3_N12.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N16.npz` | `src/certoutage/data/SIG_m3_N16.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N20.npz` | `src/certoutage/data/SIG_m3_N20.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N24.npz` | `src/certoutage/data/SIG_m3_N24.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N32.npz` | `src/certoutage/data/SIG_m3_N32.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N48.npz` | `src/certoutage/data/SIG_m3_N48.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N64.npz` | `src/certoutage/data/SIG_m3_N64.npz` | identical copy |
| `campaigns/t20/banques/SIG_m3_N8.npz` | `src/certoutage/data/SIG_m3_N8.npz` | identical copy |
| `campaigns/t20/banques/commun.npz` | `src/certoutage/data/commun.npz` | identical copy |
| `campaigns/t20/banques/m2_N8.npz` | `src/certoutage/data/m2_N8.npz` | identical copy |
| `campaigns/t20/banques/m3_N8.npz` | `src/certoutage/data/m3_N8.npz` | identical copy |
| `campaigns/t20/code/composer.py` | `src/certoutage/_runtime.py` | selection of the Nakagami units128 grid |
| `campaigns/t23/banques/N64.npz` | `src/certoutage/data/m1_N64.npz` | identical copy |
| `campaigns/t23/banques/N8.npz` | `src/certoutage/data/m1_N8.npz` | identical copy |
| `campaigns/t23/banques/SIG_12.npz` | `src/certoutage/data/SIG_12.npz` | identical copy |
| `campaigns/t23/banques/SIG_16.npz` | `src/certoutage/data/SIG_16.npz` | identical copy |
| `campaigns/t23/banques/SIG_32.npz` | `src/certoutage/data/SIG_32.npz` | identical copy |
| `campaigns/t23/banques/SIG_48.npz` | `src/certoutage/data/SIG_48.npz` | identical copy |
| `campaigns/t23/banques/SIG_64.npz` | `src/certoutage/data/SIG_64.npz` | identical copy |
| `campaigns/t23/banques/SIG_8.npz` | `src/certoutage/data/SIG_8.npz` | identical copy |
| `campaigns/t24g_gamma/RESULTATS_gain_exact_gamma.json` | `tests/regression/fixtures/gamma.json` | identical copy |
| `expected/campaign_decisions/D1.json` | `tests/regression/fixtures/D1.json` | identical copy |
| `expected/campaign_decisions/D1_POINTS.csv` | `tests/regression/fixtures/D1_POINTS.csv` | identical copy |
| `expected/campaign_decisions/D2.json` | `tests/regression/fixtures/D2.json` | identical copy |
| `expected/campaign_decisions/D2_POINTS.csv` | `tests/regression/fixtures/D2_POINTS.csv` | identical copy |
| `expected/campaign_decisions/D3.json` | `tests/regression/fixtures/D3.json` | identical copy |
| `expected/campaign_decisions/D3_POINTS.csv` | `tests/regression/fixtures/D3_POINTS.csv` | identical copy |
| `expected/campaign_decisions/MINORANTS_N20.json` | `src/certoutage/data/MINORANTS_N20.json`; `tests/regression/fixtures/MINORANTS_N20.json` | identical copy |
| `expected/campaign_decisions/MINORANTS_N24.json` | `src/certoutage/data/MINORANTS_N24.json`; `tests/regression/fixtures/MINORANTS_N24.json` | identical copy |
| `nakagami/code/grouped.py` | `src/certoutage/_vendor/nak_grouped.py` | relative imports; loading replaced by a subclass in _runtime.py |
| `nakagami/code/thermal.py` | `src/certoutage/_vendor/nak_thermal.py`; `src/certoutage/_runtime.py` | relative imports; loading replaced by a subclass in _runtime.py; constructor without chdir; rectangles and masses unchanged |
| `ppp/code/champ.py` | `src/certoutage/_generate.py` | pure function; configurable M; trivial bound if the Fourier remainder exceeds 1; same arrays tested at equal M |
| `ppp/code/commun.py` | `src/certoutage/_vendor/commun.py` | relative imports; Arb context managed by the API |
| `ppp/code/minorants.py` | `src/certoutage/api.py` | J_max: analytic distribution and integration for new cases; central certificates provided |
| `ppp/code/oracles.py` | `src/certoutage/_vendor/oracles.py`; `src/certoutage/_runtime.py`; `src/certoutage/api.py` | relative imports; loading constructors with integrity checks; numerical methods inherited unchanged; dimensioning with a configurable grid, exact decimal comparisons and new public statuses |
| `ppp/code/ppp.py` | `src/certoutage/_vendor/ppp.py` | relative imports |
| `ppp/code/thermal_backend.py` | `src/certoutage/_vendor/thermal_backend.py` | relative imports; Arb context managed by the API |
| `tables/FIGURE_1.csv` | `tests/regression/fixtures/FIGURE_1.csv` | identical copy |
| `tables/TABLE_I_CERTIFICATS.csv` | `tests/regression/fixtures/TABLE_I_CERTIFICATS.csv` | identical copy |

T28b corrections: the vendored guards, the Laplace check and the decision
contracts were then changed; the details and the proof of preservation are
in [LOGIC_CHANGES.md](LOGIC_CHANGES.md). The destination digests in
`EXTRACTION.json` describe the corrected version.

T28c preparation (0.1.0): integrity-check vocabulary harmonized, internal
function renamed `verified_bytes`. No numerical calculation changed. The
licence split was checked in the archive: see [LICENSES.md](../LICENSES.md).
The destination digests include these changes.

0.2.0 (26 November 2026): the user-facing text of the destination
files was translated into English (see [LOGIC_CHANGES.md](LOGIC_CHANGES.md)).
The `destination_sha256` digests in `EXTRACTION.json` still describe 0.1.0
(all 66 were checked against the 0.1.0 tag). The eight destinations whose
bytes changed since then carry two extra fields in their entries:
`post_release_sha256`, the digest of the current file, and
`post_release_change`. In 0.2.0, seven changed for text only, and
`_runtime.py` also carries the new cache key of the PPP/Gamma environment.
In 0.3.0, `_generate.py`, `_runtime.py` and `api.py` also carry the link
coefficients, the real path-loss exponent and the PPP domain notes; the five
`_vendor/` files are unchanged since 0.2.0 (see
[LOGIC_CHANGES.md](LOGIC_CHANGES.md)). `tests/unit/test_release.py` checks
that each recorded digest is that of the file, and that every destination
that differs from 0.1.0 is recorded (G37).
