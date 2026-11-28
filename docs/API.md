# Public API

Every public entry point is type-annotated. The objects are immutable
dataclasses; `dataclasses.asdict` gives a JSON export (replace ±∞ by a text
representation for strict JSON when a threshold is censored).

## Model and calculation

`Model(N=24, lam="0.1", eta=4, convention="C-TX", m=1, R0=1,
d1="80/3", d2=160, g=1)` validates the
scope documented in the README (Scope). Real parameters are read through
their decimal representation: use strings to state an intended decimal
number exactly. Booleans, NaN, infinities (except d1/d2 as below) and
uncovered cases are rejected.
The parameter `m` describes the two elementary powers, not a Gamma
approximation of the total gain.

`user=1` selects d1 and `user=2` selects d2; no other physics depends on
the user index. d1 and d2 lie in [10⁻¹², 10¹²], or are positive infinity
written exactly as `"inf"` or `math.inf`. g is zero or in [10⁻¹², 10¹²].
These three fields accept `int`, `Fraction`, `Decimal`, decimal or `"p/q"`
strings, and floats read by their shortest decimal representation. They are
stored as reduced rational strings (`"26.5"` becomes `"53/2"`), or `"inf"`.
R0 stays 1 and `lam` remains λ′R0². `eta` accepts exact decimal strings,
`int`, `Decimal`, and floats read by their shortest decimal spelling, in
[2.1, 8]. Rational strings such as `"7/2"` are rejected. Values exactly 3
or 4 are stored as those integers (`3.0`, `"3.00"` and `Decimal("3")`
share the same model, cache key and bank); other values are canonical
plain decimal strings (`"3.50"` becomes `"3.5"`, `5.0` becomes `"5"`).
General exponents use the Arb 2F1 identities and generated PPP/Gamma arrays
(provisional proofs in [PROOFS.md](PROOFS.md)). When a PPP inversion contributes, the
contract records the transform and whether the analytic remainder criteria
of [D_M](CONTRACT.md#on-demand-ppp-inversion) are proved; results with
lam=0 or g=0, infeasible allocations and analytic floors carry no such note.
Outside D_M the enclosure remains valid but may be wide; a third note
flags the trivial regime λ ≥ 13.37(η−2) (tau*a0 >= 1), where it carries no
information. At eta=3,4 the
explicit paths, banks and contract notes are unchanged.

Before exact conversion to a fraction, nonzero decimal inputs must have
adjusted exponent in [-4000, 4000]. This applies to link inputs, eta,
`SNRGrid` and `Enclosure.format(scale=...)`. Zero spellings such as
`"0e-1000000000"` pass where zero is admissible. Rational `"p/q"` strings
retain their separate parsing path and Python's integer digit limit.

`Model.from_link(*, p1="0.3", p2="0.7", theta1=1, theta2=None,
ell1="1/8", ell2="1/64", **fields)` reads finite, strictly positive link
inputs in the same exact way. `theta2=None` uses theta1. It computes
c2=theta2/(p2-theta2*p1), c1=max(theta1/p1,c2), then d1=c1/ell1 and
d2=c2/ell2, entirely with `Fraction`. Other Model fields may be passed;
supplying d1 or d2 raises `TypeError`. A derived d outside its domain raises
`ValueError` naming the coefficient. The defaults give exactly `Model()`.

If p2-theta2*p1≤0, both coefficients become `"inf"` before any division.
For a selected infinite d, outage, floor and largest-interferer queries
return the analytic interval [1,1], with an infeasible-allocation note;
`required_snr` returns `excluded` (`inconclusive` for Chernoff). This rule
also holds in C-INR and at g=0.

Finite d rescales the argument of the existing signal bank outward.
Below its range the lower bound is 0; above it the upper bound is 1.
No new signal bank is generated. The narrower m=2,3 bank range may give
wide intervals and `inconclusive` decisions after rescaling.

`Numerics(precision_bits=160, ppp_dft_power=18, bank_policy="auto")` controls
the calculations of a query. `bank_policy="fresh"` regenerates the PPP or
Gamma distribution; the signal bank is still the provided or prepared one. From 160 to
1024 bits and M from 2^12 to 2^20 are accepted. An insufficient grid widens
the intervals. Larger choices use more memory and time.

`outage_enclosure(model, user, snr_db, *, gain="exact", interference="PPP",
numerics=Numerics())` returns `Enclosure(lower, upper, contract)`. The SNR is
finite, in dB, in [-1000, 1000]. `floor` takes the same parameters except
`snr_db`. The case without PPP is obtained with `lam=0` or
`interference="none"`, or with `g=0`. At g=0 the requested interference
label is retained, a note records the absent contribution, and the floor
and largest-interferer bound are analytically [0,0] for finite d.

The `gain` options are `exact`, `eq3` and `chernoff`; `interference` is
`PPP`, `Gamma`, `mean` or `none`. The public name `eq3` avoids saying
"gauss" without naming the comparator. The historical internal identifiers
`gauss` and `GAMMA` do not appear as public method names.

`Enclosure.as_dict()` returns the raw floats. `format(scale="1e-5",
places=4)` divides the interval by the scale and rounds **outward**: it
takes the exact rational quotient of the binary64 bounds by the decimal
scale, then an integer floor and ceiling, independently of the `decimal`
context. In Table II, Eq. (3) + Gamma is displayed with three decimals and
the first two rows with four, as in the manuscript.

## Dimensioning

`required_snr(model, user, target, grid=SNRGrid(), *, gain="exact",
interference="PPP", numerics=Numerics())` accepts 0 < target < 1.
`SNRGrid(start=-40, stop=96, step="0.0625")` is explicit; all its parameters
are multiples of 1/128 dB, and stop-start is a multiple of the step.
Validation is exact and rational; the values stored in binary64 are exactly
representable and are used directly by the search.

The result, an `SNRDecision`, contains:

- `status`: `feasible`, `excluded` or `inconclusive`;
- `lower_db`, `upper_db`: the threshold bracket when feasible; -∞ on the left
  if the start of the grid is already feasible (no finite edge is invented);
- `floor`: the floor certificate;
- `reason`: finite threshold, censoring, exhausted grid or undecided floor;
- `undecided_points`: the number of points between the two finite edges;
- `scope` and `contract`: what the decision is about, and the provenance of
  the finite queries, even when the analytic C-INR floor uses no bank;
- `target`: the decimal target of the decision, kept also for exclusions,
  inconclusive searches and the J_max row.

The binary search keeps its bounds by monotonicity of the outage and checks
the two final points again. Excluding requires a lower bound strictly above
the target. An upper bound ≤ target is enough to certify a point. A target
equal to an endpoint is compared exactly, in decimal, with the binary value
of the float, with no numerical tolerance.

For `gain="chernoff"`, the threshold is that of the **sufficient Chernoff
rule**, not a bracket of the optimal outage threshold. The lower bound of
the comparator cannot exclude the physical model: the status stays
`inconclusive` when its floor exceeds the target.

`threshold_difference(a, b)` requires two finite, uncensored, feasible
thresholds with the same target, the same user and the same N, m, λ, η, R0,
convention, d1, d2 and g. Equivalent rational spellings of the link fields
are compared exactly (`"0.25"` equals `"1/4"`); equivalent decimal spellings
of the other fields are accepted. The gain comparator and the
interference model may differ, so that approximations can be compared.
A missing target or comparison parameter, for instance in a decision built
by hand, is rejected with `ValueError`. The function subtracts directly:
`[a.lower - b.upper, a.upper - b.lower]`. For the total error, compare
Eq. (3) + mean with exact + PPP directly; do not add two intervals that
contain a shared threshold.

## Comparisons

`compare_approximations` returns six `ComparisonRow` objects. Each row holds
its floor certificate, its decision and, possibly, a `diagnostic`.

`falsely feasible` requires a proven PPP exclusion and a feasible finite SNR
for the approximation. `masked` requires exact + Gamma (or mean) to be
falsely feasible and the replacement of the gain by Eq. (3) to exclude that
approximation. The diagnostic does not change the certified quantity.

`largest_interferer_bound(model, user)` encloses the lower bound on the TX
floor, E F_W(d_i g J_max). In C-INR, the corresponding floor is exactly zero
for finite d. The central cases N=20/24, Rayleigh, λ=0.1 or 1, η=4, user 1,
d1=80/3 and g=1 load their final certificates.
The other cases compose, on demand, the analytic distribution of J_max with
the useful-gain bank. A provided certificate always reports
`precision_bits=160`, with no new integration, whatever precision is
requested in `numerics`.

`Contract.parameters` ends with d1, d2 and g in that order, in canonical
form. Its assumptions record the actual link coefficients and interference
gain, including infeasible allocations. At the Letter's defaults the
assumptions and numerical bounds are unchanged.

Every contract also carries `interval_library`, for instance
`python-flint 0.9.0 / Arb-Acb`: the version of python-flint imported by the
running process, read when the result is built. It names the loaded Python
binding, not the version of the FLINT C library that binding was built
against, and it says nothing about the origin of stored banks or
certificates: for a `provided-certificate` or `analytic` result, no Arb
computation takes place.

## Integrity and concurrency

A SHA-256 mismatch raises `IntegrityError` before `numpy.load`.
`allow_pickle=False` is enforced. `clear_cache()` frees the calculation
objects and forces verification on the next reads. Changing a bank on disk
does not retroactively change arrays that are already loaded.

The global Arb context is restored after each call, including when an
exception is raised. Calls into this package are serialized by a lock. Other
software changing `flint.ctx` in parallel does not take part in this lock:
use separate processes in that situation. No cluster parallelism is required
or started.

## Explicit preparation

`Model(N=...)` accepts every exact Python integer in [8, 64]; bools,
floats and numeric strings are refused. The eight embedded sizes remain
8, 12, 16, 20, 24, 32, 48 and 64. Construction performs no I/O.
Chernoff is available for Rayleigh m=1 throughout [8, 64], with or without
interference; it is refused for m=2,3 with the generation-scope error.

`prepare(model, *, gain="exact", dry_run=False, fetch=False) -> tuple[PreparedBank, ...]`
is the explicit preparation step, offline by default. With `fetch=True`, it
first calls `fetch_banks(model.N)` and then calculates anything still missing.
Retrieval errors propagate; they never trigger calculation as a fallback.
`dry_run=True` always suppresses retrieval, even with `fetch=True`. Exact and Eq. (3) share banks.
It prepares the read set for all queries of the model and gain, plus missing
inputs in dependency order. Embedded inputs take priority and verified cache
entries are reused. It never prepares a PPP/Gamma environment; these remain
on demand. All bank calculation uses 160 bits and one thread, restoring the
caller's arithmetic context even on failure. Local calculation writes only
`<cache>/generated/`; explicit retrieval also uses `<cache>/fetched/`. The fixed thermal ratio is passed as the exact Fraction(10).

`PreparedBank` is frozen, with `logical`, `stored_name`, `origin`, `sha256`,
`bytes`, `seconds` and `estimated_seconds`. Preparation origins are `embedded`,
`fetched`, `cached` and `generated`; a dry-run plan uses `missing` for absent banks. Its digest
and size are then None, and its stored name is None until all input digests
are known. `seconds` measures the operation; `estimated_seconds` is a pair
of estimated minimum/maximum seconds on one CPU core for a missing bank.
The plan uses metadata only, does no calculation or writing, and is suitable
for `dataclasses.asdict`. See [cost estimates](REGENERATION.md#generation-scope-reachable-through-prepare).

A query missing a required bank raises public `BankNotAvailable(LookupError)`
before any thermal or PPP calculation, naming the missing logical banks,
a `fetch_banks(N)` call with the approximate archive size from the pinned
index, and the exact prepare call with its estimated calculation cost. Present corrupt banks raise
`IntegrityError`; preparation never silently repairs them. Analytic results
retain their analytic contracts, but the query's route is checked for bank
readiness first. A generated read bank sets `Contract.source` to
`generated-banks`, even when the environment is also calculated locally.
The receipt contains its stored name and SHA-256. Notes record logical name,
N, m, thermal ratio 10, 160 bits, generation version and descriptor versions
of certoutage, python-flint and NumPy. Chernoff notes also explain its
machine-dependent initial-guess bytes. No thermal field is added to Model
or Contract.parameters.

## Explicit bank retrieval

`fetch_banks(*sizes, url=None, directory=None, timeout=60.0) -> tuple[PreparedBank, ...]`
installs the precomputed set for the requested sizes. Pass one or more exact
Python integers in [8, 64], or `Model` objects (their N is used). Booleans and
nonintegers are refused. Duplicates are merged, and sizes are processed in
ascending order. For the full set, use `fetch_banks(*range(8, 65))`.
There is one archive per N, except 20 and 24, which need none. The common
bank and the large direct-route banks required by that N are fetched only
when absent from the package and the verified local store.

No published location is registered in this development version. Locations
are selected in this order: explicit `url=`, nonempty `CERTOUTAGE_BANKS_URL`,
then the package's ordered mirrors (currently empty). A location is a
`{file}` template or a base with `/` and the filename appended. HTTPS is
required, except HTTP to `127.0.0.1`, `::1` or `localhost`. Up to five redirects
are allowed, and every destination is checked. TLS uses the default verified
context and no proxies. Certificate failures explain `SSL_CERT_FILE`, a CA
bundle from `certifi`, and manual download followed by `directory=`.

For an offline deposit already on disk:

```python
from certoutage import fetch_banks
banks = fetch_banks(8, 21, 63, directory="/path/to/deposit")
```

`url` and `directory` are mutually exclusive. A nonempty `CERTOUTAGE_OFFLINE`
other than `0` refuses every retrieval without `directory=` before any socket
is opened. The timeout is a finite positive number of seconds, applied to
network operations. With all target banks already verified, no transfer is
made (offline mode still requires `directory=`).

Each archive, bank and descriptor is checked against byte counts and SHA-256
digests in the package's byte-pinned `data/BANK_SET.json`. The five large
embedded copies use the existing `data/MANIFEST.json` pins. Downloaded
manifests are never trusted. Streaming is bounded by the pinned file size;
temporary `.part` files are deleted on success, failure and interruption.
All archive members must match the exact pinned set, names, regular-file
types, sizes and digests before any member is installed. Validation uses
`extractfile`, without extraction filters or automatic tar extraction.

Public `BankDownloadError(BankNotAvailable)` reports transport failures,
including offline mode, missing locations, HTTP/TLS errors and disallowed
redirects. Only transport failures try the next configured mirror; the final
error lists every attempt and preserves its cause. Any nonconforming content
raises `IntegrityError` immediately, with no mirror retry. Neither error
starts calculation or returns an `inconclusive` result. Python without `lzma`
can still import the package; reading an archive raises `BankDownloadError`.

A valid existing bank is never replaced. A different valid local Chernoff
variant is preserved and reported with a warning; its digest can make the
published thermal bank unreachable. Corrupt pairs raise `IntegrityError`;
a lone bank or descriptor can be completed. After installation, all seven
fading/gain combinations of every requested N must have no `missing` entry
in `prepare(..., dry_run=True)`, otherwise `BankNotAvailable` identifies the
missing entries and any preserved input conflict. An earlier successfully
installed archive is retained if a later archive fails.

The returned tuple has one `PreparedBank` per targeted bank, with its logical
name, stored name, verified digest, byte count and elapsed `seconds`.
`estimated_seconds` is None. `embedded` means a package copy, `cached` means
a verified existing local copy, and `fetched` means a newly installed copy.
Archives install schema-1 pairs in `generated/`, so queries using them have
`source="generated-banks"` and the usual generated-bank provenance. Copies
of the five large embedded banks retain their original receipts, notes and
contracts. The wheel still includes all its banks.

## Bank store

The store distinguishes `embedded`, `generated` and `fetched` origins.
For a name in the embedded manifest, resolution first uses the package file
if present, then `<cache>/fetched/<name>`, otherwise raises `BankNotAvailable`
with a `certoutage.fetch_banks(N)` hint. Every fetched load checks the same
manifest digest and size as the embedded copy. Other logical names resolve
to schema-1 pairs in `generated/`. Only explicit preparation or retrieval
writes banks; queries never retrieve them automatically.

The cache location is resolved on every call: nonempty `CERTOUTAGE_CACHE_DIR`,
otherwise nonempty absolute `XDG_CACHE_HOME` plus `/certoutage`, otherwise
`~/.cache/certoutage` (also on Windows). Relative XDG paths are ignored.
`CERTOUTAGE_CACHE_DIR` is used as given: `~` is not expanded and a relative
value, like a relative `HOME`, depends on the current directory, so set an
absolute path.
Generated banks live in `generated/`. Only `fetch_banks` creates `fetched/`,
for verified copies and temporary transfers. Importing or reading creates no
directory or file. A present package file always has priority over the cache;
corruption of that file is an error, not a reason to fall back.

A generated name hashes the canonical JSON of its family, exact flat
parameters and generator name/version. Parameters accept strings, integers
and booleans; encode reals as exact decimal or `float.hex` strings. Its JSON
descriptor is checked for schema, identity, byte count and SHA-256 before
loading immutable arrays without pickle. Production families additionally
check exact array keys, dtypes, shapes, finite probability bounds, grids and
identity scalars N, m and B where stored. The schema remains 1. Thermal
identities include the canonical rational `thermal_ratio="10"`, the common
bank digest and the exact gain or Chernoff input digest. Input digests are
read from the embedded manifest or the generated input's JSON descriptor,
without loading its arrays. Removing an input makes its thermal bank unready.
The recorded source digest is metadata, not checked at read time; generator
name and version are part of the hashed identity. Invalid data raises `IntegrityError`;
a missing bank or descriptor raises public `BankNotAvailable(LookupError)`
with the name and cache directory, never a fallback. Absences are not cached.

Local generation through `_store_generated` uses deterministic NPZ entries
and temporary files in the destination directory: bank first, descriptor last.
Retrieval uses the same atomic writer and commit order after archive validation.
Array keys
match `[A-Za-z0-9_]{1,64}`, and the serialized bytes must decode to the
requested arrays. A verified existing pair with the same arrays is left
untouched; a corrupt pair, or one holding different arrays under the same
identity, raises `IntegrityError`. A directory in place of a bank or
descriptor raises `IntegrityError`; a file in place of the `generated`
directory means an absent bank.
Permission errors propagate; Windows replacement retries are limited to 20
at 50 ms intervals. This detects accidental corruption and inconsistent
writes, not an adversary rewriting both bank and descriptor (G38–G44).
