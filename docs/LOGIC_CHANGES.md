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

## English text throughout (26 November 2026, unreleased)

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

## Display of threshold differences (26 November 2026, unreleased)

| Area | Change | Justification and check |
|---|---|---|
| `models.ThresholdDifference.format` | `Decimal.quantize` under an inherited `localcontext()` replaced by exact rational scaling and integer floor/ceiling, as in `Enclosure.format`; the sign follows the binary64 value | With `traps[Inexact]` set by the caller, the old code raised `decimal.Inexact` (no wrong value, a loud failure). Old and new outputs compared on 112,224 cases (places 0 to 30, values in ±2000 dB, multiples of 1/128, ±0.0, subnormals): identical. Test `test_display_of_threshold_differences_ignores_decimal_traps` |

No certified quantity is involved: the change is in the display only.

## Cache key of the PPP environment (26 November 2026, unreleased)

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

## Interval engine named at run time (26 November 2026, unreleased)

| Area | Change | Justification and check |
|---|---|---|
| `models.Contract.interval_library` | The fixed default `"python-flint 0.9.0 / Arb-Acb"` became a `default_factory` that reads `flint.__version__` when the contract is built. No code passes the field explicitly | Under python-flint 0.9.0 the string is unchanged, so is every fixture (Table II included, not regenerated). The field names the imported binding, not the FLINT C library, and is present also when nothing is computed in Arb (`provided-certificate`, `analytic`); see API.md. Guarantee G36 |

`models.py` was not listed among the certifying files when this change
was made; it is now (CONTRIBUTING.md). Its other change on this branch,
`ThresholdDifference.format`, is declared above.
