# Regenerating the banks

Normal queries need neither the network nor the archive. The generators
below are separate local tools; they publish nothing and submit no job. The
shipped package keeps the original banks and their manifest. A regeneration
never replaces these files automatically.

## PPP and Gamma: included generator

From the root of the package:

```sh
python tools/regenerate_ppp.py --lam 0.2 --eta 3 --kind PPP --power 18 --output work/PPP_l0p2_e3.npz
python tools/regenerate_ppp.py --lam 0.2 --eta 3 --kind GAMMA --output work/GAMMA_l0p2_e3.npz
```

For the historical settings: `--power 20 --bits 160`. The four arrays and
their SHA-256 digests are printed. The compressed NPZ container may have a
different digest with unchanged arrays. PPP/Gamma generation for λ=0.2,
η=3, M=2^18 was compared with a copy of the original generator in which
only M was changed: the eight arrays have the same bytes.

## Gain, thermal, Chernoff and J_max: copies of the v7 archive

The archive must be available locally. Install `.[regenerate]` for SciPy,
which only the historical generators use. `ARCHIVE` stands here for a path
to be replaced explicitly; there is no network discovery.

```sh
python tools/regenerate_from_archive.py --archive /path/to/archive_v7 --output work/rayleigh24 --kind signal --N 24
python tools/regenerate_from_archive.py --archive /path/to/archive_v7 --output work/chernoff24 --kind chernoff --N 24
python tools/regenerate_from_archive.py --archive /path/to/archive_v7 --output work/nakagami2_8 --kind nakagami --m 2 --N 8
python tools/regenerate_from_archive.py --archive /path/to/archive_v7 --output work/largest24 --kind largest --N 24
```

Each command requires a new directory outside the archive. It copies the
required sources and records their digests in `COPIES.json` before running.
Only the mandatory access to the scheduler metadata is made optional
(`os.environ.get` instead of indexing). The archive stays read-only. The
historical absolute environments and submission commands are not used.

`signal` recomputes the common thermal grid, the Rayleigh amplitude
inversion and the signal bank. `chernoff` recomputes the common grid, the
amplitude and the propagated Chernoff bank. `nakagami` recomputes the
amplitude and the signal from the T20 sources, reusing the common thermal
bank provided by the archive. `largest` recomputes the J_max distribution
and its integration, but reuses the package's integrity-checked useful-gain
bank and the archive's reference table of floors.

The common bank can also be recomputed separately, in the copied directory,
by running `thermal_backend.common()` (or `t4_backend.common()` for T20). The
Table I amplitude banks correspond to the files
`campaigns/t23/banques/N8.npz`, `N64.npz` and
`campaigns/t20/banques/m2_N8.npz`, `m3_N8.npz`. The Table I Chernoff banks
come from `banks_extra/C_N8.npz` and `C_N64.npz`; their specific generator is
`nakagami/code/chernoff_bank.py` (copy the folder before running it).

The full N=24 regeneration has not been run so far. A replay of queries,
the lossless repackaging of a bank and its construction from scratch must
not be confused. The central J_max values are the archived **final
certificates**, not a new bank of its distribution rebuilt during the
extraction.

## Transport and integrity

`data/MANIFEST.json` gives the digest of each loaded file, its size and its
sources. `docs/EXTRACTION.json` details the copy and repackaging operations.
The central text banks are checked on the CSV bytes, then on the array
bytes, before lossless recompression into NPZ.

For a new version of the banks, update the data, their manifest and the
manifest digest pinned in `_banks.py` after validation. Never just replace a
file to get around `IntegrityError`. The regression tests must then decide
explicitly whether the new version preserves the raw bounds or requires a
different version.
