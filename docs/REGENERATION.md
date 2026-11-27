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
the other seven sizes, initially overlapping the N=24 run. In particular,
almost every grouped N=8 point and every grouped N=12 point needs J=13, while
those for N>=20 stop at J=9.

A second replay ran on a Linux compute node (Python 3.12.3, python-flint
0.9.0, NumPy 2.5.3), one single-core task per size, with the thermal-cell
correction in place (default kappa=10). It gave the same result: every
array identical, and the same file-level matches. Gain generation took 23 to
24 seconds per size; signal generation 15 to 16 minutes at N=8 and 12,
9 minutes at N=16, and 6 to 7 minutes at N=20 to 64; peak resident memory
was 0.43 to 0.45 GiB per task. Timings depend on the machine and its load.


## Ported Nakagami and Chernoff generators

These pure internal entries require only NumPy and python-flint. The public
API still admits its existing model sizes and Chernoff cases. From the
package root, use a new or empty output directory:

```sh
python tools/generate_gain.py --N 21 --m 2 --signal --output work/nak2_21
python tools/generate_gain.py --N 21 --m 3 --signal --output work/nak3_21
python tools/generate_gain.py --N 21 --chernoff --signal --output work/chernoff21
python tools/compare_gain_banks.py --archive /path/to/archive_v7 --generated work/nak2_21 --m 2 --packaged src/certoutage/data
python tools/compare_gain_banks.py --archive /path/to/archive_v7 --generated work/chernoff8 --chernoff --mode overlap --packaged src/certoutage/data
```

Nakagami outputs are `m{m}_N{N}.npz` (uncompressed, seven arrays, including
scalar m) and `SIG_m{m}_N{N}.npz` (compressed, units128/exact/gauss).
Chernoff outputs are `C_N{N}.npz` and `SIG_C_{N}.npz`, uncompressed as in
the archive. Root statistics are added to the gain JSON, not to the NPZ.
The Rayleigh command keeps its earlier `N{N}.npz` filename; its logical
bank identity in the scope descriptor is `m1_N{N}.npz`.

`--points A:B` and `--merge PART...` also work for these families. Raw
Nakagami indices run from 0 to 1024 on (-4096+8*j)/128 dB; raw Chernoff
indices run from 0 to 5120 on (j-2048)/32 dB. Nakagami merging preserves
raw values and omits levels. Chernoff merging tightens and expands to 20481
nodes, retaining its 5121 raw levels. Parts must cover the whole grid
exactly once. The internal `kappa` keyword is an exact nonnegative
Fraction, default 10; no public model parameter is added.

For Chernoff, `--mode bytes` tests array identity, while `--mode overlap`
checks every interval intersection and records the maximum relative
endpoint difference where both endpoints exceed 1e-300. Refined levels
may differ in overlap mode; domain metadata must agree. Missing references
are errors, not evidence of agreement. Historical central lower/upper gain
keys are normalized to chernoff_lo/chernoff_hi for comparison.

The local full-size measurements (Python 3.12.3, python-flint 0.9.0,
NumPy 2.5.3) took about 19.4 s and 15.3 s for m=2 and m=3 gain at N=24,
and 1.4 s and 4.3 s for Chernoff gain at N=8 and 64. The latter overlapped
all 524289 nodes, with maximum relative endpoint differences below 2.3e-16.
Twenty-point thermal samples including setup averaged 0.082 s (m=2,N=8),
0.116 s (m=3,N=8), and 0.046 s (Chernoff,N=64) per point. These short-sample
costs include table conversion; they are not full-bank timing estimates.
Process peak RSS was 554 MiB. Times depend on machine load.

### Generation scope (unreleased; not yet reachable from the API)

The descriptor names the complete dependency closure for the current
adapters, with the existing `commun.npz` as a shared input:

| Gain | m | N | Banks to generate | Functions / status |
|---|---|---|---|---|
| exact, eq3 | 1 | integers 8..64 | m1_N{N}, SIG_{N} | gain_arrays, signal_arrays |
| exact, eq3 | 2,3 | integers 8..64 | m{m}_N{N}, SIG_m{m}_N{N} | gain_arrays, nakagami_signal_arrays |
| chernoff | 1 | integers 8..64 | m1_N{N}, SIG_{N}, C_N{N}, SIG_C_{N} | gain_arrays, signal_arrays, chernoff_arrays, chernoff_signal_arrays |
| chernoff | 2,3 | any | none | ValueError: Rayleigh comparator only |
| any | other m, booleans or nonintegers | any | none | ValueError: integer recurrence domain |
| any | any | outside 8..64, booleans or nonintegers | none | ValueError: announced generation domain |
| gamma, gg, other names | any | any | none | ValueError: gain generator not ported |

For Chernoff alone the numerical comparator requires C_N and SIG_C.
The extra Rayleigh banks above make the current adapters and J_max path
complete: direct thermal loading also reads m1_N, interference loading
also reads SIG, and J_max uses exact SIG. Every named generator is available.
The existing central J_max certificates are optional stored results; its
on-demand distribution has no further N/m-dependent input. A future API
integration must connect this closure to model validation, bank lookup and
preparation; this change does not do so.


### Full eight-size replay

A 24-task Linux replay used Python 3.12.3, python-flint 0.9.0 and NumPy
2.5.3, one CPU per task. All sixteen Nakagami gain banks matched all seven
arrays and the original uncompressed file hashes. All sixteen signal banks
matched the three archived arrays. Preserving their Fortran layout then
reproduced every original Linux signal-file hash; local recompression of
the same arrays instead matches the separate recompressed archive hashes.
Both authenticated container hashes are accepted by the comparator.

| N | m=2 gain / signal (s) | m=3 gain / signal (s) | Chernoff gain / signal, default guess (s) |
|---|---|---|---|
| 8 | 24.6 / 46.6 | 24.6 / 47.6 | 3.0 / 188.6 |
| 12 | 24.9 / 51.3 | 25.5 / 52.6 | 7.8 / 256.3 |
| 16 | 25.0 / 49.8 | 25.1 / 54.2 | 6.9 / 222.8 |
| 20 | 25.2 / 53.4 | 25.3 / 56.4 | 7.1 / 211.2 |
| 24 | 25.0 / 53.4 | 25.5 / 56.7 | 8.0 / 201.5 |
| 32 | 25.2 / 54.8 | 26.1 / 57.7 | 6.5 / 138.7 |
| 48 | 25.5 / 55.9 | 25.6 / 56.4 | 8.7 / 132.2 |
| 64 | 25.0 / 55.0 | 25.6 / 56.4 | 10.5 / 127.9 |

The eight Chernoff gain and signal banks were generated without importing
SciPy. Every interval overlapped wherever an embedded reference exists:
C_N8, C_N64, SIG_C_20 and SIG_C_24. Maximum relative endpoint differences
were respectively 2.18e-16, 2.23e-16, 2.82e-16 and 3.02e-16. The other
sizes have no embedded Chernoff reference; generation is not a claim of
archival identity there.

With the historical initial guess injected, C_N64 and SIG_C_20/24 matched
the embedded arrays exactly. C_N20/24 matched an independent historical
point-kernel and bank-loop replay; their old intermediate gain files are
absent from the archive. C_N8 initially differed by a few last-bit values
on one Linux node, then matched both the independent historical replay
and the embedded bank exactly on another node. Thus library versions alone
do not ensure initial-guess bit identity across platforms. Certification
still comes only from the Arb signs; default generation uses overlap checks.
The historical root counts were recovered: 4289 at N=8 and 14199 at N=64.

The longest numerical task took about 7.2 minutes, including both default
and injected preparations at N=20. Peak process RSS was below 0.45 GiB
for the numerical tasks. Subsequent checks changed only Nakagami array
storage order and compared existing outputs; no data shipped in the package
was replaced. Raw gain containers remain uncompressed as in the archive;
small transport copies may be compressed without altering array bytes.
