# Changelog

## Unreleased

- Joint (λ, η) announcement: near η = 2 the useful λ range is bounded
  above (λ_τ ≈ 6.52(η−2)), and for λ ≥ 13.37(η−2), possible only when
  η < 2.748, the enclosure is trivial. CONTRACT.md tabulates the domain, a
  third contract note flags the trivial regime (PROOFS.md, Proposition 4.7;
  G65). No numerical result changes.
- `docs/PROOFS.md`: provisional proofs of the statements the 0.3.0 contract
  cannot refer to the Letter for (link and gain scaling, the two 2F1
  identities, the Fourier bound, R and τ for every η > 2, the domain D_M,
  the cumulants of J). § 6 of PROOFS.md says which statements have a test
  with reference values from outside the package, which only sample tests,
  and which none (G63). New checks: the Fourier majorant, the remainder on a
  distribution with explicit CDF, the DFT identification at the nodes, the
  derivatives of the remainder, and the transform near η = 2.
- PPP transform and D_M notes now appear only when a PPP inversion
  contributes: they are no longer attached to λ=0, g=0, infeasible or analytic
  results. No numerical result changes.
- Documentation of the general interface: Scope of the README, contract and
  API updated for free d1, d2, g and real η; new example
  `examples/free_parameters.py`.
- Free real path-loss exponent eta in [2.1, 8] (planned 0.3.0), read exactly
  and normalized before cache/bank selection. Explicit eta=3,4 paths stay
  bit-identical; other values use Arb 2F1 and a certified Pfaff fallback.
- Compute and announce the joint analytic remainder domain D_M, without
  changing valid coarse results outside it. Independent quadrature, DFT,
  full-grid overlap and offline API checks cover the extension (G54–G62).
- Bound decimal exponents before exact fraction conversion in model inputs,
  SNR grids and enclosure formatting; extreme zero spellings remain valid.

- Free exact link coefficients d1, d2 and interference gain g (planned 0.3.0),
  with `Model.from_link` and analytic handling of infeasible allocations.
- Outward signal-bank scaling and direct thermal integration for arbitrary
  admitted links; g=0 removes interference. Letter-default bounds remain
  bit-identical, and numerical cache keys are unchanged.
- Contracts record canonical d1, d2 and g; `threshold_difference` checks
  them exactly. Offline link tests and guarantees G45–G53 cover the extension.
- Internal bank store: verified local generated banks, deterministic NPZ writes,
  atomic replacement and explicit missing-bank errors. Embedded banks always
  take precedence; public queries and numerical results are unchanged.
- Reserve `generated-banks` in contracts and the `fetched` origin for 0.4.0.
- Offline bank-store tests cover corruption, cache isolation, interrupted writes
  and four concurrent processes; new guarantees G38–G44.
- Independent review of the bank store, corrected before merging: the writer
  refuses a stored bank whose arrays differ from the requested ones under the
  same identity, checks that its bytes decode to the requested arrays and
  restricts array keys to `[A-Za-z0-9_]{1,64}`; a directory in place of a bank
  or descriptor raises `IntegrityError`, a file in place of the cache
  directory means an absent bank; a new test checks that no public query
  reaches the generated-bank store (G44).
- Documentation: `docs/PARAMETERS.md` lists every model parameter, whether it
  is fixed or free, which version is planned to free it, and what must hold
  first. Unreleased link coefficients and interference gain are now marked free.

## 0.2.0 — 2026-11-26

No change in the numerical results: every regression, Table II included,
is identical bit for bit to 0.1.0.

- Continuous integration: `.github/workflows/tests.yml` installs the package
  (non-editable) and runs the suite on Ubuntu (Python 3.10 to 3.14), macOS and
  Windows (Python 3.11 and 3.14).
- New test `tests/regression/test_table_ii_example.py`: the output of
  `examples/table_ii.py --json` must reproduce Table II bit for bit (floats
  compared through `float.hex`; only `wall_seconds` is excluded). No change
  in the calculations.
- `.gitattributes` (`* text=auto eol=lf`, `*.npz binary`): a Windows clone
  (`core.autocrlf=true`) rewrote `data/MANIFEST.json` with CRLF line endings,
  so its SHA-256 digest no longer matched, and an installation from such a
  clone refused every calculation (`IntegrityError`, as designed). Found by
  the first continuous-integration run. The PyPI files (wheel and sdist,
  built with LF line endings) were not affected.
- Tests read files as UTF-8 explicitly. On Windows, the default encoding
  (cp1252) could not read the "—" of the changelog headings and made
  `test_release_versions_and_dates_agree` fail.
- All text in English: exception messages, docstrings, contract assumptions,
  example output, test comments, documentation and changelog. Exception
  messages change wording, not type. Numbers are unchanged; the Table II
  fixture changes in eight strings only (see `docs/LOGIC_CHANGES.md`).
- Support: `SUPPORT.md`, issue forms (feature request, bug report, question)
  and a README section explaining how to ask for a missing feature. Issue
  tracker and changelog links added to the package metadata.
- Register of guarantees `docs/GUARANTEES.md`: 34 promises at first (36 with
  G35 and G36 below, 37 with G37), each with the
  file that keeps it and the tests that check it, and a list of the stated
  promises not yet checked by a test; a meta-test fails if a row cites a
  missing test or file. New direct tests for the guarantees that had none or
  only partial ones: no unpickling, read-only and cached banks, no network
  access, no file written, safe outputs of the regeneration tools, guards
  under `python -O`, no reachable `assert`, Arb context restored after an
  exception, one lock, valid probability intervals, digests recorded in the
  contract, comparability checks of `threshold_difference`, input bounds.
- Fix: `ThresholdDifference.format` raised `decimal.Inexact` when the
  caller's decimal context trapped inexact results. It now uses exact
  rationals, like `Enclosure.format`. Output is unchanged otherwise
  (112,224 cases compared, including -0.0 and subnormals). Found by the
  review of the register.
- `CONTRIBUTING.md`: how to report, propose a change and run the tests, and
  the fail-closed rule every change must keep. README: installation from
  PyPI (`pip install certoutage`) instead of a supplied wheel, the tested
  platforms, and a continuous-integration badge. Package classifiers list
  Python 3.10 to 3.14 and Linux, macOS and Windows, as tested.
- Performance: the PPP and Gamma environments are cached on what they depend
  on (intensity, path-loss exponent, interference model, M, precision, bank
  policy) instead of the whole model, so changing N, m, the convention, the
  user or the gain no longer repeats the Laplace inversion. A sweep over the
  eight sizes and both conventions at a new intensity takes 5.9 s instead of
  65.6 s. Every result of the test suite is unchanged bit for bit (see
  `docs/LOGIC_CHANGES.md`). New guarantee G35 with two tests.
- `Contract.interval_library` is read from the python-flint actually imported
  (`flint.__version__`) when a result is built, instead of being a fixed
  string. With python-flint 0.9.0 the text is unchanged
  (`python-flint 0.9.0 / Arb-Acb`), and so is the Table II fixture.
  Dependency policy written in `CONTRIBUTING.md`: python-flint stays pinned
  exactly until another version passes every regression bit for bit. New
  guarantee G36 with two tests.
- Continuous integration runs the suite once more under `python -O`
  (Ubuntu, Python 3.13).
- Corrections after an independent review of this branch (no numerical
  change): `docs/EXTRACTION.json` had a stale digest for `_runtime.py` and
  described its change as translation only, although it also carries the
  new cache key; both fixed, and a new test (G37) checks that every digest
  in the inventory is that of the current file. `models.py` is now listed
  among the certifying files, and the run-time reading of
  `interval_library` is declared in `docs/LOGIC_CHANGES.md`. The
  documentation says that `interval_library` names the python-flint binding,
  not the FLINT C library. `examples/table_ii.py` prints the computed
  threshold instead of a fixed string, and rounds its last displayed bound
  outward through exact rationals. The register states which guarantees are
  tested on a few cases only, and lists three more documented promises that
  no test checks yet. A test checks that the version and the release date
  quoted in the README are those of the package, and that the python-flint
  version quoted there is the pinned one (G34).

## 0.1.0 — 2026-11-24

- First version prepared for publication: name `certoutage`, embedded banks,
  and the Table II results preserved identically.
- Public README in English, explicit scope, and a chronological provenance
  that separates the archive which produced the results from this later
  extraction.
- PEP 639 metadata, notices and the BSD-3-Clause AND MIT AND CC-BY-4.0 split;
  consistent CITATION.cff and codemeta.json.
- SHA-256 integrity vocabulary and internal function `verified_bytes`; tests
  of the versions and of calculations stopping on a digest mismatch.
- Wheel and sdist meant for a self-contained installation, with no data
  download at run time. No change in the numerical calculations.

## T28b corrections, 24 November 2026 (0.1.0.dev1, unreleased)

- Exact validation of `SNRGrid`, independent of the `decimal` context;
  outward display through an exact rational quotient, with no intermediate
  rounding.
- Laplace check of the PPP generator restored at the three points of the
  archive, including for the coarse branch; explicit errors under
  `python -O`.
- Nine invariants of the vendored modules `commun`, `ppp` and
  `thermal_backend` move from `assert` to `ArithmeticError`; numerical
  calculations preserved.
- Actual precision of the provided certificates (160 bits), the `fresh`
  message and the contract of the stored CDF bound at B corrected.
- Target kept in `SNRDecision.target`; threshold differences refused for
  incompatible targets, users or physical parameters.
- `str()` behaviour of `np.float32(0.1)` fixed by a test and stated in the
  README. Audit tests, binary regressions and a clean installation checked
  in T28b.

## 0.1.0.dev1, 24 November 2026

First local phase, unreleased. Typed API for the model, outage, floor,
dimensioning, the Gamma/mean/Eq. (3) comparators, the J_max bound and
Chernoff. Integrity-checked v7 banks; local PPP generation for a new
intensity. Raw regression of the central claims, Table I, Figure 1 and
Nakagami. Table II and new-case examples; documentation of the contract and
its limits.
