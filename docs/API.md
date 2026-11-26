# Public API

Every public entry point is type-annotated. The objects are immutable
dataclasses; `dataclasses.asdict` gives a JSON export (replace ±∞ by a text
representation for strict JSON when a threshold is censored).

## Model and calculation

`Model(N=24, lam="0.1", eta=4, convention="C-TX", m=1, R0=1)` validates the
scope documented in the README (Scope). Real parameters are read through
their decimal representation: use strings to state an intended decimal
number exactly. Booleans, NaN, infinities and uncovered cases are rejected.
The parameter `m` describes the two elementary powers, not a Gamma
approximation of the total gain.

`Numerics(precision_bits=160, ppp_dft_power=18, bank_policy="auto")` controls
the calculations of a query. `bank_policy="fresh"` regenerates the PPP or
Gamma distribution; the signal bank is still the provided one. From 160 to
1024 bits and M from 2^12 to 2^20 are accepted. An insufficient grid widens
the intervals. Larger choices use more memory and time.

`outage_enclosure(model, user, snr_db, *, gain="exact", interference="PPP",
numerics=Numerics())` returns `Enclosure(lower, upper, contract)`. The SNR is
finite, in dB, in [-1000, 1000]. `floor` takes the same parameters except
`snr_db`. The case without PPP is obtained with `lam=0` or
`interference="none"`.

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
thresholds with the same target, the same user and the same N, m, λ, η, R0
and convention. Equivalent decimal spellings are accepted; the gain and the
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
floor. In C-INR, the corresponding floor is exactly zero. The central cases
N=20/24, Rayleigh, λ=0.1 or 1, η=4, user 1 load their final certificates.
The other cases compose, on demand, the analytic distribution of J_max with
the useful-gain bank. A provided certificate always reports
`precision_bits=160`, with no new integration, whatever precision is
requested in `numerics`.

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
