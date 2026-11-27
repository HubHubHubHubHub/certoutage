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

The archive must be available locally. `--kind signal` and `--kind largest`
do not need SciPy. Install `.[regenerate]` for the `chernoff` and `nakagami`
historical generators. `ARCHIVE` stands here for a path
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
`campaigns/t20/banques/m2_N8.npz`, `m3_N8.npz`. For Rayleigh N=8 and N=64,
compare only the six common arrays (`N`, `B`, `exact_lo/hi`, `gauss_lo/hi`):
the original ten-array files also contain unused `gamma` and `gg` comparators.
The same distinction applies to N=16 and N=32. The Table I Chernoff banks
come from `banks_extra/C_N8.npz` and `C_N64.npz`; their specific generator is
`nakagami/code/chernoff_bank.py` (copy the folder before running it).

The complete historical N=24 regeneration was run on 27 November 2026:
`N24.npz`, `SIG_24.npz` and `commun.npz` matched the original files byte for
byte with python-flint 0.9.0 and NumPy 2.5.3. On one core, gain generation
took about one minute, signal generation 8 to 20 minutes across historical
and replay measurements; peak memory was 0.44 GiB. The central J_max values
are the archived **final certificates**, not a newly rebuilt distribution
bank from the extraction.

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


## Ported gain generator

The internal pure generator needs python-flint and NumPy, without SciPy or
access to the archive. The CLI owns all writes and requires a new or empty
output directory. Its RSS accounting uses Unix `resource.getrusage` (Linux
and macOS); the pure generators do not depend on this module. Production uses M=2^19 and 160-bit Arb arithmetic; the
private Python `power` argument (10 through 19) is only for reduced-grid
tests. N must be an integer in [8,64]. This does not extend `Model` or add a
public preparation/cache interface.

```sh
python tools/generate_gain.py --N 24 --output work/gain24 --signal
python tools/generate_gain.py --N 24 --output work/part_a --points 0:10000
python tools/generate_gain.py --N 24 --output work/part_b --points 10000:20481
python tools/generate_gain.py --N 24 --output work/merged --merge work/part_a/SIG_24_points_0_10000.npz work/part_b/SIG_24_points_10000_20481.npz
python tools/compare_gain_banks.py --archive /path/to/archive_v7 --generated work/gain24
```

A points run also computes its gain bank. Parts contain raw bounds and
refinement levels; only explicit merging applies the final monotone
accumulations. Overlaps and holes are errors. Each NPZ has a JSON sibling
with elapsed time, process-lifetime peak RSS in bytes, Python/library
versions and file/array digests, without hostnames or absolute paths.
The comparator prints per-array results and writes `comparison.json`
(or `--json FILE`). `--packaged PATH` additionally compares signal arrays
with that package's data directory. When comparing the archive references themselves, it recognizes their
compressed files separately from original uncompressed file hashes; a six-array gain
file at N=8,16,32,64 must differ from its ten-array original.

The complete eight-size ported replay was checked locally on macOS with
Python 3.12.3, python-flint 0.9.0 and NumPy 2.5.3. All six common gain arrays
and all three signal arrays matched the archive byte for byte. Gain files
at N=12,20,24,48 and all signal files matched their original file hashes;
the other four gain containers differ as expected because they omit gamma/gg.
Signal arrays also matched the package banks. Measured gain times ranged
from 13.5 to 60.4 seconds, signal times from 8.1 to
25.6 minutes, and process peak RSS from 0.30 to 0.46 GiB.
N=24 was started separately; a pool of three single-thread processes handled
the other seven sizes, initially overlapping the N=24 run. These are elapsed local measurements, not cluster
benchmarks. In particular, almost every grouped N=8 point and every grouped
N=12 point needs J=13, while those for N>=20 stop at J=9. No cluster replay
was performed.
