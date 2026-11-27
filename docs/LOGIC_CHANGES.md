# Logic changes and proofs of preservation

The v7 archive is not modified. Relative imports, paths and loading are not
enough to describe the whole extraction: the following changes are declared
explicitly.

| Area | Change | Justification and check |
|---|---|---|
| `oracles.Environment.point`, `Signal.indices/lookup` | Numerical bodies kept through inheritance | D1/D2/D3: same raw points, same decisions and same differences; Gamma: all central rows |
| Bank loading | Sources injected in memory after SHA-256 check; no more `chdir` or `ROOT/banques` in the active path | CSV→NPZ repackaging checked on array digests; negative corruption test |
| Environment selection | Exact decimal equality with 0.1/1 before choosing a bank | Prevents a new intensity close to a historical one from using the wrong bank by rounding of the file name |
| Nakagami | `units128` grid of T20, instead of assuming the Rayleigh grid | Twenty T20 cases reproduced, three comparators when evaluated; no interpolated extension of the CDF |
| Table I | Thermal constructor without relative files; historical grouped sums | Eighteen queries at the endpoints of the nine finite cells identical; Eq. (3) cell, N=8, 40 dB excluded |
| PPP generation | `champ.py` becomes a function without writes; configurable M | Remainder formulas recomputed with the actual M. At λ=0.2, η=3, M=2^18: PPP and Gamma arrays bit-identical to a copy of the original generator with the same M |
| Fourier remainder too large | If R>1, coarse CDF [0,1] and analytic tail at B, without DFT | Trivial inclusion of the probabilities; protects binary64 transport for extremely small λ. Test at λ=1e-500; no rare-event accuracy claimed in this branch |
| Threshold search | Grid given by the user; left censoring `feasible`, threshold [-∞, first feasible point] | One feasible point is enough; no excluded endpoint is invented. Dedicated test; exact preservation of the historical uncensored brackets |
| Decision outside the grid | `inconclusive`, even if every finite point tested is excluded | Only the floor can prove impossibility at every SNR. Tests for an exhausted grid and for the floor |
| Chernoff | A floor of the upper bound above the target gives `inconclusive`, never `excluded` for the outage | Restores the correct meaning of the v7 replay; keeps the values and brackets of the sufficient rule |
| Arb context | No permanent change of `ctx` at import; precision and threads restored under a lock | Test with an external 80-bit context, a 192-bit calculation and return to 80; banks explicitly kept at 160 bits |
| Display | Outward decimal rounding, explicit scale; exact rational quotient since T28b | Published strings of the four central claims; extra test at the 1/128 dB step |
| Diagnostics | `falsely feasible` / `masked` derived from the statuses | Table II test and explicitly documented conditions; no physical verdict induced by the comparator alone |
| J_max | Central final certificates read; integration for other cases | Identical raw central bounds; analytic distribution and envelopes kept for the new λ |

`_generate.py` keeps the remainder formulas of the archive. The parts that
choose the grid, manage the context, load data and decide have changed: the
regression is therefore not presented as an "interface only" extraction.
The detailed T28 evidence is kept in `evidence/` at the level of the
extraction mission; the tests shipped with the package are self-contained.

## T28b corrections after the Fable audit (24 November 2026)

| Finding | Change | Preservation and test |
|---|---|---|
| M1 | `SNRGrid` validated with `Fraction`, then search in integer units of 1/128 dB | No decimal context takes part in the operations; bounds limited to ±1000 dB and step ≤2000, hence exactly representable binary multiples. Tests at precision 3, including with active rounding traps, and the counterexample 1.0001 rejected |
| M2 | `Enclosure.format` divides exactly in rationals and applies floor/ceiling to the displayed decimal units | For exact q, floor(q·10^p)/10^p ≤ q ≤ ceil(q·10^p)/10^p. No intermediate rounding; cases with scales of 451 decimals, a 500-digit quotient and an exact boundary |
| M3 | Laplace check of `ppp/code/champ.py:67–76` restored (omitted in T28); `ArithmeticError` | Three points s=0.1, 0.5 and 1, same masses and Arb inequalities as the archive; the R>1 branch is checked too. No array changed. Tests of the calls and injection of an inconsistent transform |
| M4 | Nine `assert` statements replaced by explicit guards in three vendored files, detailed below | Conditions and numerical operations preserved. Bad inputs rejected under `python -O` too; outputs of every regression compared in binary64 before and after |
| M5 | No change in how reals are read; one test and one README sentence added | `np.float32(0.1)` is still read through `str()` and selects the 0.1 bank; the test already passed on T28 |
| M6 | `fresh` message naming PPP and Gamma; `provided-certificate.precision_bits=160`; contract of the CDF at B corrected | Bounds unchanged; the λ=0.01 test shows a looser last node with DFT. The last correction is about the text only |
| M7 | New field `SNRDecision.target`; target/user/convention/N/m/λ/η/R0 checked before a threshold difference | Exact decimal equality; gain/interference comparators allowed to differ. Exported decisions carry an extra `target` field; bounds, statuses and diagnostics preserved |

The vendored changes are exactly:

- `_vendor/commun.py`: `out` checks finiteness and outward transport;
  `poisson_tail` checks n>κ (three guards).
- `_vendor/ppp.py`: `envelopes` checks L≤U and a zero origin, then
  nonnegative masses (two guards).
- `_vendor/thermal_backend.py`: `tighten` checks L≤U; `outward` checks
  finiteness and outward transport; `gamma_series` checks x>0 and k>0
  (four guards). The four guards analogous to those cited in M4 were
  converted so that these three modules keep the same safety behaviour
  under optimization.

The M3 check is a consistency net, not an independent proof: for exp(−sJ),
a decreasing function, the masses on `xlo` bound the transform from above
and those on `xhi` from below; the residual mass at +∞ contributes zero.
The check is `lap_lo.lower() <= exact.upper()` and
`lap_hi.upper() >= exact.lower()`, as in the archive, without tightening
the CDFs.

The T28b traces in `evidence/t28b/` at the level of the mission keep the
counter-tests on the old code, the digests of the outputs before and after,
the comparisons of the examples with the T28 JSON files, and the run times
of the normal and optimized suites in a fresh environment. Run times are not
reproducible outputs; the `target` addition is declared and checked
separately when the JSON exports are compared.

## English text throughout (26 November 2026, 0.2.0)

All user-facing text is now in English: exception messages, docstrings,
the `Contract.assumptions` strings, example output, the comments and
docstrings of the tests, the documentation and the help of `tools/`. In
`_vendor/`, only the nine exception messages added in T28b and four
comments or docstrings were translated. No condition, operation or control
flow changed. The one code-level edit outside string literals is in
`threshold_difference`, where the label `"usager (user)"` became `name`.

Output changes are text only. `examples/table_ii.py --json` was compared
with the previous fixture value by value: same structure, same 30 binary64
values (`float.hex`), same integers, booleans and `None`. Exactly eight
distinct strings changed: the six assumptions and the two
"(raw probability)" annotations. The regression fixture
`tests/regression/fixtures/table_ii.json` was regenerated after this check.
The numbers in every other regression fixture are unchanged.
The eight destination files whose bytes changed since 0.1.0 are listed in
`EXTRACTION.json`: `post_release_sha256` is the digest of the current file,
`post_release_change` says what changed. For `_runtime.py` this includes the
cache key below. `tests/unit/test_release.py` checks that each recorded
digest is that of the file, and that every changed destination is recorded.

## Display of threshold differences (26 November 2026, 0.2.0)

| Area | Change | Justification and check |
|---|---|---|
| `models.ThresholdDifference.format` | `Decimal.quantize` under an inherited `localcontext()` replaced by exact rational scaling and integer floor/ceiling, as in `Enclosure.format`; the sign follows the binary64 value | With `traps[Inexact]` set by the caller, the old code raised `decimal.Inexact` (no wrong value, a loud failure). Old and new outputs compared on 112,224 cases (places 0 to 30, values in ±2000 dB, multiples of 1/128, ±0.0, subnormals): identical. Test `test_display_of_threshold_differences_ignores_decimal_traps` |

No certified quantity is involved: the change is in the display only.

## Cache key of the PPP environment (26 November 2026, 0.2.0)

| Area | Change | Justification and check |
|---|---|---|
| `_runtime.environment` | The cache key was `(model, kind, numerics)`. It is now `(lam, eta, kind, precision_bits, ppp_dft_power, bank_policy)`, through a new cached `_environment`; `environment` keeps its signature. Size of the cache unchanged (12). New guard: `_environment` raises `ArithmeticError` if the current Arb precision differs from the precision in its key | `Environment.__init__` reads only `model.lam`, `model.eta`, `kind`, `numerics.ppp_dft_power`, `numerics.bank_policy` and the Arb precision set by the caller; N, m, the convention, the user and the gain enter only through `point()`, which does not modify the object. So the key is complete and sharing an environment between models cannot change a result. Remark of the Fable audit of 24 November 2026: a sweep in N or a change of convention repeated the Laplace inversion |

Preservation was checked by recording every result computed during the
whole test suite before and after the change (5,079 calculations,
12,535 binary64 values, compared through `float.hex`, with their
contracts and the exceptions raised): no difference. Table II is unchanged
bit for bit. A sweep of 16 queries at a new intensity (lam=0.3, eta=4,
N in all certified sizes, both conventions, default numerics, M=2^18) gives
the same 16 enclosures and contracts, with one Laplace inversion instead of
16: 5.9 s instead of 65.6 s on the development machine. New guarantee G35,
with two tests; each of seven mutations (one element dropped from the key,
or the precision guard removed) makes one of them fail.

## Interval engine named at run time (26 November 2026, 0.2.0)

| Area | Change | Justification and check |
|---|---|---|
| `models.Contract.interval_library` | The fixed default `"python-flint 0.9.0 / Arb-Acb"` became a `default_factory` that reads `flint.__version__` when the contract is built. No code passes the field explicitly | Under python-flint 0.9.0 the string is unchanged, so is every fixture (Table II included, not regenerated). The field names the imported binding, not the FLINT C library, and is present also when nothing is computed in Arb (`provided-certificate`, `analytic`); see API.md. Guarantee G36 |

`models.py` was not listed among the certifying files when this change
was made; it is now (CONTRIBUTING.md). Its other change on this branch,
`ThresholdDifference.format`, is declared above.

## Bank store (26 November 2026, 0.3.0)

`_banks` now resolves embedded and locally generated banks through one
verified reader; `fetched` is reserved and raises `NotImplementedError`.
Generated names identify exact parameters and generator name/version.
Strict per-bank descriptors check this identity, SHA-256 and size before
deserialization. An explicit internal writer emits deterministic NPZ bytes
and replaces temporary files in order, bank then descriptor, without a
global lock. Missing pairs raise `BankNotAvailable`; corrupt pairs raise
`IntegrityError`. Neither becomes a fallback. No generated data or absence
is cached in memory, so `api.clear_cache()` needs no change.

Embedded reading retains the pinned manifest, priority over the user cache,
the module-level `files` lookup at each read and the original exceptions.
`arrays` still calls the module-level `verified_bytes`; `manifest.cache_clear`
and `receipt` are unchanged. `models.Contract.source` gains only the reserved
`generated-banks` literal. No public query calls the writer or produces this
source; branch selection, existing contracts and regression fixtures are
unchanged. Offline tests check altered banks and descriptors, read-only and
absent caches, byte-identical serialization across timestamps, interrupted
writes, Windows retry limits and four concurrent spawn processes. The
embedded shadow test compares bounds with `float.hex` and the full contract.
The existing regressions and the new store tests run normally and under
`python -O`; targeted mutations check the new guarantees G38–G44.

Preservation was checked by recording every result computed during the
whole test suite before and after the change, in fresh non-editable
installations (5,234 calculations, with their contracts and the exceptions
raised, binary64 values compared through `float.hex`): no difference on the
126 existing test cases, none of which was modified. Table II is unchanged
bit for bit. Reading `SIG_24.npz` through `verified_bytes` costs the same as
before within measurement noise (paired median difference below 1 µs,
under 0.1 % of loading its arrays).

Corrections after the independent review of the bank store (same day, before
merging; `_banks.py` only, generated origin and writer only): (1) the writer
compared nothing when a verified pair already existed under the requested
name, so a generator changed without a new version left the old arrays in
place silently; it now compares the stored arrays (keys, dtype, shape, bytes)
with the requested ones and raises `IntegrityError` on any difference. A
change of generator code under the same name and version is still not
detected at read time, and `code_sha256` stays recorded, not checked; the
module docstring and the threat model now say so instead of "changed
generators". (2) Array keys containing a NUL byte were truncated by the ZIP
writer, so a verified pair could lose or rename an array; keys are now
restricted to `[A-Za-z0-9_]{1,64}` (all 26 keys of the embedded banks match),
and the writer checks that its serialized bytes decode to the requested
arrays before writing. (3) `NotADirectoryError` while reading a generated pair
now means an absent bank (`BankNotAvailable`); `IsADirectoryError` raises
`IntegrityError`; `PermissionError` still propagates. The embedded reading
path, `verified_bytes`, `arrays`, `manifest`, `receipt` and every public
query are unchanged; no regression fixture changes.

## Link coefficients and interference gain (26 November 2026, 0.3.0)

Model now stores exact canonical d1, d2 and g, with the Letter defaults
80/3, 160 and 1. Model.from_link computes the perfect-SIC coefficients for
two thresholds in Fraction; a nonpositive allocation margin gives infinite
coefficients before division. A selected infinite d gives analytic outage
[1,1], including the floor, before any C-INR shortcut. Chernoff retains its
inconclusive decision rule. At g=0, finite-SNR evaluation uses the atom at
zero without a residual tail, preserving the requested interference label.

The runtime overrides Environment.point to scale x by g exactly once, then
the bank argument by 3d/80. Rational factors are enclosed in binary64 before
outward multiplication. The identity returns the input arrays unchanged;
the factor 6 retains the original operations. J_max uses the combined
factor 3dg/80, retaining products only when exact Fraction comparisons prove
they are representable; stored certificates require d1=80/3 and g=1 in
addition to the previous conditions. Neither the law of J nor its cumulants
see g. The moment call is documented as a cumulant, with R fixed at 1.

Direct thermal evaluation dispatches on d: 80/3 keeps the grouped path,
160 keeps the historical user-2 path, and other admitted values use the
same grouped rectangle loop with an outward Arb amplitude sqrt(101*d/rho)
passed in the call. No link coefficient enters cached object state.
Environment and thermal cache signatures and keys are unchanged, and
_vendor/, _generate.py, _banks.py, data and fixtures are untouched.

Contracts append canonical d1, d2 and g and derive assumptions from the
model; the default assumptions tuple is unchanged. threshold_difference
requires equal link fields, compared with Fraction (or the string inf),
and rejects missing ones. Comparison-row labels include g when needed and
report the infeasible C-INR limit as 1. The old numerical regressions, an independent
before/after capture of ten cases using float.hex, and offline tests of
exact input validation, outward products including subnormals, bank
extension, scaling identities, user equivalence and cache reuse check the
extension (G45–G53). Direct/bank checks assert overlap, not equal widths.
The second cumulant and the generated Gamma CDF are checked against mean
kappa_1 and variance kappa_2 at eta=3,4.
Targeted mutations exercise double gain, inward scaling, missing comparison
fields, cached d, infeasibility, zero-gain tails, stored certificates, user
routing and the identity factor.

Existing test changed: regression/test_table_ii_example.py adds the three
new default fields to the expected model and contract parameters in memory.
The archived fixture, every historical expected field and every float.hex
comparison remain unchanged. This is the declared contract-schema change;
no numerical regression expectation is weakened or replaced.


## Real path-loss exponent (26 November 2026, 0.3.0)

Model reads eta as an exact decimal in [2.1,8], retaining integers 3 and 4
at those exact values and otherwise storing a plain canonical decimal
string. Equivalent spellings share cache keys and filenames. Only canonical
int 3/4 can reuse embedded PPP/Gamma banks; other exponents generate arrays.
The numeric adapter leaves these two integers unchanged at every historical
Arb arithmetic site. _vendor/, data, _banks.py and regression fixtures are
untouched; no public exports are added.

The new _transform module delegates eta=3,4 directly to the archive and
uses the two hypergeometric identities otherwise. It calls 2F1 on z with
abc=True, checks finiteness and relative radius against 2^(-prec/2), retries
once at doubled precision and then uses the Pfaff series with the entire
omitted tail enclosed by |T_N|/(1-|q|). Its branch choice uses the midpoint
of |s|, with both identities valid on the required Re(s)>0 half-plane.

Pure helpers compute R, tau and certified lambda boundary brackets for
D_M. General-exponent PPP contracts append transform and inside/outside
notes; the explicit-path contracts stay character-for-character unchanged.
These criteria concern analytic node width only. The public numerical grid
range stays 2^12 to 2^20; domain helpers also accept 2^6 to 2^11 within the
monotone M>=42 regime, permitting a small-grid empty-window check. No
outside-domain rejection is added. The regeneration tool accepts eta text
and emits its canonical JSON form.

A single decimal exponent guard precedes exact Fraction conversion for
link fields, eta, SNRGrid and Enclosure.format. Nonzero adjusted exponents
outside [-4000,4000] raise ValueError promptly; zero with any exponent stays
zero. Rational p/q strings keep their existing path.

Tests check exact explicit midpoints/radii and array bytes, all M=2^12
frequencies against the explicit integral, M=2^16 array overlap and widths,
and independent Acb quadrature of the bounded real integral for eight
exponents. Nonanalytic endpoint evaluation restricts v to its nonnegative
real integration path; analytic evaluation rejects balls touching Re(v)<=0
for noninteger powers. Forced fallback failures and truncated Pfaff tails,
direct DFT sums, monotonicity, domain corners, contracts and decimal input
checks exercise the new behavior (G54–G62). Three float.hex snapshots are
explicitly labelled non-independent; separate before/after captures and
the existing regressions check preservation at eta=3,4. Targeted mutations
exercise the dispatch, abc flag, argument order, remainder, normalization,
C2 sign, exponent guard, bank naming and tail-window sign.

Existing test changed: unit/test_contracts.py removes only dict(eta=3.0)
from test_invalid_models. Accepting 3.0 as canonical int 3 is a declared
API change, covered positively by test_eta_canonicalization and the cache
and bank-name test. No numerical regression assertion is changed.

## Domain notes only when a PPP inversion contributes (27 November 2026, 0.3.0)

`api._contract` attached the two general-exponent notes (2F1 transform,
inside/outside D_M) to every PPP query with eta other than 3 or 4
(noninteger, or an integer from 5 to 8). They were
misleading when no inversion takes place: lam=0 (the environment is the
exact point mass at 0), g=0 (the environment is `none`), an infeasible
allocation (analytic [1,1]) and analytic floors (C-INR, or no PPP). The notes
are now added only for a nonanalytic result with lam≠0 and g≠0. Bounds,
sources, digests, parameters and assumptions are unchanged; only the `notes`
of these contracts lose the two entries. The explicit eta=3,4 contracts are
unchanged.

Existing test changed: `unit/test_real_eta.py::test_real_eta_all_natures`
expected the notes on the analytic C-INR floor; it now expects them exactly
when the source is not `analytic`. New test:
`::test_domain_notes_only_when_a_ppp_inversion_contributes`. No numerical
regression assertion is changed. A capture of every result of the suite
before and after (6,155 calculations, compared by `float.hex`) differs only
in these notes: in the declared test and in the three λ=0 PPP corners of
`::test_technical_domain_corners`, whose assertions do not read notes.

In the same change, the docstrings of `_transform.py` refer to the
propositions of `docs/PROOFS.md` instead of working labels, and attribute
Johansson's reference to Arb's 2F1 evaluation only; no code line changes.
`_transform.py` is not an extracted file and has no entry in EXTRACTION.json.

## Note for the trivial regime τa0 ≥ 1 (27 November 2026, 0.3.0)

An independent review (S19) found that, near η = 2, large intensities give
[~0, 1] enclosures with only the generic "outside D_M ... may be wide"
note. New helper `_transform.aliasing_exceeds_one(lam, eta, power)` proves
τ ≥ expm1(20), i.e. τa0 ≥ 1 (PROOFS.md, Proposition 4.7); uncertainty
returns False. `api._contract` appends a third note exactly when it holds,
on the results that already carry the two general-exponent notes. Bounds,
sources, digests, parameters, assumptions and the two existing notes are
unchanged. No existing test is changed; new tests
`unit/test_real_eta.py::test_trivial_regime_above_the_aliasing_threshold`
and `::test_lambda_window_near_two`. A before/after capture of the suite
is compared by `float.hex` (session S19b).
