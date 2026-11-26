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
R0 stays 1 and `lam` remains λ′R0²; eta remains an integer in {3, 4}.

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
Gamma distribution; the signal bank is still the provided one. From 160 to
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

## Bank store (internal; used from 0.4.0)

The internal store distinguishes `embedded`, `generated` and the reserved
`fetched` origin. No current public query uses the generated-bank store or
its writer. `Contract.source` reserves `generated-banks`: not produced by any
query in this version; planned for 0.4.0. The `fetched` reader raises
`NotImplementedError`; its future digests will be pinned in code.

The cache location is resolved on every call: nonempty `CERTOUTAGE_CACHE_DIR`,
otherwise nonempty absolute `XDG_CACHE_HOME` plus `/certoutage`, otherwise
`~/.cache/certoutage` (also on Windows). Relative XDG paths are ignored.
`CERTOUTAGE_CACHE_DIR` is used as given: `~` is not expanded and a relative
value, like a relative `HOME`, depends on the current directory, so set an
absolute path.
Generated banks live in `generated/`; `fetched/` is never created. Importing
or reading creates no directory or file. Embedded names always resolve to
the package, regardless of cache contents.

A generated name hashes the canonical JSON of its family, exact flat
parameters and generator name/version. Parameters accept strings, integers
and booleans; encode reals as exact decimal or `float.hex` strings. Its JSON
descriptor is checked for schema, identity, byte count and SHA-256 before
loading immutable arrays without pickle. Invalid data raises `IntegrityError`;
a missing bank or descriptor raises internal `BankNotAvailable(LookupError)`
with the name and cache directory, never a fallback. Absences are not cached.

Only `_store_generated` writes, using deterministic NPZ entries and temporary
files in the destination directory: bank first, descriptor last. Array keys
match `[A-Za-z0-9_]{1,64}`, and the serialized bytes must decode to the
requested arrays. A verified existing pair with the same arrays is left
untouched; a corrupt pair, or one holding different arrays under the same
identity, raises `IntegrityError`. A directory in place of a bank or
descriptor raises `IntegrityError`; a file in place of the `generated`
directory means an absent bank.
Permission errors propagate; Windows replacement retries are limited to 20
at 50 ms intervals. This detects accidental corruption and inconsistent
writes, not an adversary rewriting both bank and descriptor (G38–G44).
