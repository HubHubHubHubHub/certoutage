# Licenses and attribution

The distribution's SPDX expression is **BSD-3-Clause AND MIT AND CC-BY-4.0**.
These licenses apply together to different components; this is not a choice
of licenses for the whole package. Copyright (c) 2026 Victor Rabiet.

This allocation was checked against the original archive's `LICENSE`,
`METADATA.json` and the source files identified in
[EXTRACTION.json](docs/EXTRACTION.json), including their SHA-256 digests.
The archive explicitly assigns MIT to original executable source and
CC BY 4.0 to original numerical data and explanatory texts.

## Code

Paths below are relative to this source distribution. Paths under
`src/certoutage/` become `certoutage/` in the wheel.
For mixed files, MIT applies to the extracted portions and BSD-3-Clause to
new author contributions. See [LOGIC_CHANGES.md](docs/LOGIC_CHANGES.md) for
numerical guards changed during extraction.

| Distributed file | License | Archive source / attribution and modifications |
|---|---|---|
| `src/certoutage/_vendor/commun.py` | MIT | Victor Rabiet; `ppp/code/commun.py`; relative imports, precision context managed by the API, three assertions replaced by explicit errors |
| `src/certoutage/_vendor/ppp.py` | MIT | Victor Rabiet; `ppp/code/ppp.py`; relative imports, two assertions replaced by explicit errors |
| `src/certoutage/_vendor/thermal_backend.py` | MIT | Victor Rabiet; `ppp/code/thermal_backend.py`; relative imports, precision context managed by the API, four assertions replaced by explicit errors |
| `src/certoutage/_vendor/oracles.py` | MIT | Victor Rabiet; `ppp/code/oracles.py`; relative imports |
| `src/certoutage/_vendor/nak_thermal.py` | MIT | Victor Rabiet; `nakagami/code/thermal.py`; relative imports, loading replaced by the runtime subclass |
| `src/certoutage/_vendor/nak_grouped.py` | MIT | Victor Rabiet; `nakagami/code/grouped.py`; relative imports, loading replaced by the runtime subclass |
| `src/certoutage/_generate.py` | BSD-3-Clause AND MIT | Victor Rabiet; `ppp/code/champ.py`; pure function, configurable DFT size, coarse remainder branch, explicit Laplace guards |
| `src/certoutage/_runtime.py` | BSD-3-Clause AND MIT | Victor Rabiet; `ppp/code/oracles.py`, `nakagami/code/thermal.py`, `campaigns/t20/code/composer.py`; constructors without chdir, integrity-checked loading, Nakagami grid, locking and caches |
| `src/certoutage/api.py` | BSD-3-Clause AND MIT | Victor Rabiet; `ppp/code/oracles.py`, `ppp/code/minorants.py`; sizing and largest-interferer composition adapted into the public API, explicit contracts and validation |
| `src/certoutage/__init__.py`, `src/certoutage/_banks.py`, `src/certoutage/models.py`, `src/certoutage/_vendor/__init__.py`, `src/certoutage/py.typed` | BSD-3-Clause | New package code and typing marker by Victor Rabiet |
| `examples/*.py`, `tools/*.py`, `tests/**/*.py` | BSD-3-Clause | New examples, wrappers and tests by Victor Rabiet; regeneration tools copy archive programs only when explicitly run, with their archive license still applicable |

Thus the complete list of distributed files containing archive MIT code is
the six named vendor modules plus `_generate.py`, `_runtime.py` and `api.py`.
The archive's IEEEtran class and MPFR/MPFI source tarballs are not distributed
in this package; their LPPL/LGPL licenses do not enter its SPDX expression.
Runtime dependencies are installed separately and retain their own licenses.

## Data and documentation

For every archive-derived data file, attribution is:

> Victor Rabiet (2026), *Reproducibility archive for "Certified Outage Bounds
> for RIS-Assisted NOMA with Source-Side Thermal Energy Harvesting"*,
> archive v7 (metadata version 1.1), https://doi.org/10.5281/zenodo.24450534.
> Licensed under Creative Commons Attribution 4.0 International:
> https://creativecommons.org/licenses/by/4.0/.

The following table records all modifications to those data. Individual
source paths and source/destination SHA-256 digests are in `EXTRACTION.json`.
No changes to numerical values were made.

| File or pattern | License | Changes / attribution |
|---|---|---|
| `src/certoutage/data/SIG_20.npz`, `SIG_24.npz`, `SIG_C_20.npz`, `SIG_C_24.npz`, `PPP_l0p1_e3.npz`, `PPP_l0p1_e4.npz`, `GAMMA_l0p1_e4.npz` (all in the same data directory) | CC-BY-4.0 | Victor Rabiet, archive above; seven banks repacked from archive CSV arrays into NPZ without loss; array digests verified during extraction |
| Remaining `src/certoutage/data/*.npz` | CC-BY-4.0 | Victor Rabiet, archive above; byte-identical copies, some filenames normalized (`N8.npz`/`N64.npz` become `m1_N8.npz`/`m1_N64.npz`) |
| `src/certoutage/data/MINORANTS_N20.json`, `src/certoutage/data/MINORANTS_N24.json` | CC-BY-4.0 | Victor Rabiet, archive above; byte-identical copies of final largest-interferer certificates |
| `tests/regression/fixtures/*.csv`, `tests/regression/fixtures/*.json` | CC-BY-4.0 | Victor Rabiet, archive above; byte-identical regression data, some filenames simplified (`RESULTATS.csv` becomes `nakagami.csv`, `RESULTATS_gain_exact_gamma.json` becomes `gamma.json`) |
| `src/certoutage/data/MANIFEST.json` | BSD-3-Clause | New generated integrity/provenance inventory by Victor Rabiet; does not relicense the bank contents |
| `README.md`, `CHANGELOG.md`, `CITATION.cff`, `codemeta.json`, `LICENSES.md`, `docs/*.md`, `docs/EXTRACTION.json`, `pyproject.toml`, `MANIFEST.in` | BSD-3-Clause | New package documentation, metadata and configuration by Victor Rabiet; archive sources credited where used |
| `LICENSE` | BSD-3-Clause notice | Full terms for the new author contributions |
| `docs/ARCHIVE_LICENSE.txt`, `src/certoutage/notices/ARCHIVE_LICENSE.txt` | Original archive notice (MIT / CC-BY-4.0 allocation) | Unmodified archive `LICENSE`, including its MIT terms, copyright notice and original third-party exceptions |
| `docs/CC-BY-4.0.txt`, `src/certoutage/notices/CC-BY-4.0.txt` | CC-BY-4.0 legal text | Unmodified archive `LICENSES/CC-BY-4.0.txt`; full terms, retained verbatim |

Build-generated `PKG-INFO`, `*.egg-info/*` and `*.dist-info/*` are metadata
for this combined distribution; embedded text retains its license above.
The wheel's `*.dist-info/licenses/` directory carries `LICENSE`, this mapping,
`docs/ARCHIVE_LICENSE.txt` and `docs/CC-BY-4.0.txt`. The runtime notice copies
are also present in the wheel and source distribution.
