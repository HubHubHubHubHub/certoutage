# Contributing to certoutage

Thank you for your interest. certoutage is maintained by one person; reports,
questions and proposals are all welcome, and every one is read. This page
says how to report a problem, how to propose a change, how to run the tests,
and the one rule every change must keep: **no guarantee weakens silently**.

## Reporting a problem or asking for a feature

Use the issue tracker and its forms (bug report, feature request,
question): <https://github.com/HubHubHubHubHub/certoutage/issues/new/choose>.
[SUPPORT.md](SUPPORT.md) says what to include and what to expect.

The most valuable report is a **certified result that is wrong**: an
enclosure that does not contain the true value, or a decision (`feasible`,
`excluded`) that does not hold. Please report it even if you are not sure;
give the version (`certoutage.__version__`), the Python version, the
operating system and the shortest code that shows it.

## Proposing a change

1. For anything beyond a typo, open an issue first and describe the change.
   The supported model is deliberately limited (*Scope* in the README):
   extending it means extending what is certified, and that needs a
   discussion of the mathematics before the code.
2. Then open a pull request against `main`. Keep it focused on one change,
   and say in its description what changes for a user.
3. Add a line under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md).
4. Code, comments, messages and documentation are in English.
5. Contributions are accepted under the license of the file they change:
   BSD-3-Clause for new code ([LICENSE](LICENSE)); see
   [LICENSES.md](LICENSES.md) for extracted code and data.

## Running the tests

Python 3.10 or later is required. From a clone of the repository:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
```

On Windows, use `.venv\Scripts\python`. Continuous integration installs the
package **non-editable** (`pip install ".[test]"`), so that the tests import
the installed package and its bundled banks, and runs the suite on Ubuntu
(Python 3.10 to 3.14), macOS and Windows (Python 3.11 and 3.14), and once
more under `python -O` (Ubuntu, Python 3.13), where Python strips `assert`
statements. A pull request must pass all of these jobs.

The suite includes regression tests that reproduce the archived results
**bit for bit**: floats are compared through `float.hex`, not with a
tolerance. `tests/regression/test_table_ii_example.py` runs
`examples/table_ii.py --json` and compares its output with a stored fixture.

## The fail-closed rule

certoutage returns bounds that are certified for a stated model. A change
may make a result less precise; it must never make a result less true, and
it must never do either without saying so. In practice:

- **Certifying files** are `src/certoutage/api.py`, `models.py`,
  `_runtime.py`, `_generate.py`, `_generate_gain.py`, `_nakagami.py`, `_chernoff.py`,
  `_banks.py`, `_prepare.py`, `_fetch.py` and `_vendor/`. `models.py`
  holds the validation of the inputs, the check that every result is a
  valid probability interval, and the outward display. A change to the
  logic of any of them is declared in
  [docs/LOGIC_CHANGES.md](docs/LOGIC_CHANGES.md): what changes, what is
  preserved, and how this was checked. For an extracted file, the digest
  recorded in [docs/EXTRACTION.json](docs/EXTRACTION.json)
  (`post_release_sha256`) and its description are updated in the same
  change; a test checks the digests.
- **Outputs are compared before and after.** For such a change, compare the
  outputs of all regression tests before and after (through `float.hex`).
  An interval that becomes **wider** is acceptable if it is declared. An
  interval that becomes **narrower** needs a new argument (a proof or a
  sharper certified bound), stated in the pull request; numerical agreement
  alone is not one.
- **Every promise has a test.** [docs/GUARANTEES.md](docs/GUARANTEES.md)
  lists each promise the package makes, the file that keeps it and the tests
  that check it; `tests/unit/test_guarantees.py` fails if a row cites a
  missing test. A new promise in the README, the API or the contract gets a
  row and a test in the same change. A promise that cannot be tested yet is
  listed in the last section of that file, not left implicit.
- **Errors stay errors.** An unsupported input raises an exception; it is
  never answered `inconclusive` and never rounded to a supported case. A
  failed integrity check raises `IntegrityError`; it never becomes a result.
  Guards must hold under `python -O`: use explicit checks that raise, not
  `assert`.
- **Data.** A new bundled bank is listed in `data/MANIFEST.json` with
  its SHA-256 digest, and its license is stated in [LICENSES.md](LICENSES.md).
  The reference digest of the manifest is pinned in `_banks.py`. Queries
  never write banks and never access the network.

## Generated-bank compatibility

`_prepare.py` owns explicit preparation, dependency plans, canonical identity,
one-core cost estimates and the private forced-reproduction audit hook.
`_banks.py` verifies schema-1 descriptors, file digests, sizes and production
array structure; public queries never invoke its writer implicitly.
Local generated banks have descriptors in `<cache>/generated/`, and never
change the bundled manifest.

`GENERATION_VERSION` in `_generate_gain.py` is part of every generated name.
`test_certifying_source_digest_is_pinned` pins `_prepare._code_sha256()`:
SHA-256 of each filename in `_SOURCE_FILES` (UTF-8), NUL, its exact source
bytes, then NUL, in the declared order. Any change to these sources requires
both updating the pin and an explicit decision about GENERATION_VERSION.
Increment it if stored arrays or their interpretation can change; document
why it can stay unchanged otherwise. The initial integration uses version
"1": added identity adapters and scope metadata leave every certifying
kernel unchanged. The descriptor records this digest, but reads deliberately
check name/version, not the current source digest.

The default preparation tests replace full generators with structurally
valid trivial bounds. Real forced generation is opt-in:
`CERTOUTAGE_SLOW_TESTS=1 python -m pytest tests/unit/test_prepare.py`.
Set `CERTOUTAGE_CACHE_DIR` for an isolated store when running examples.

## Published-bank compatibility

`_fetch.py` owns explicit verified retrieval, safe archive validation,
nonreplacement of existing banks and the all-combinations readiness check.
Changing the published set requires copying its exact manifest bytes to
`data/BANK_SET.json` and updating `BANK_SET_SHA256` together. Never obtain
trust pins from a remote manifest. The five large embedded-bank copies use
`data/MANIFEST.json` pins, which must agree with the set's embedded entries.
No mirror URL is registered until the actual files have been published.

`tests/unit/test_fetch.py` uses small synthetic banks and local HTTP servers;
it never needs a remote host. Real-deposit tests are opt-in with
`CERTOUTAGE_BANKSET_DIR=/path/to/deposit`. The private
`_banks._withhold_embedded` context manager simulates absent package files;
it is only an audit hook. Queries and dry runs must never fetch implicitly.

## Dependency policy

Every certified bound is computed by Arb, through python-flint, so the
version of python-flint is part of what a result means:

- **python-flint is pinned exactly** (`python-flint==0.9.0` in
  `pyproject.toml`, and the same in `codemeta.json`). It moves to a new
  version only in a release, after every regression has been run again with
  that version and found bit for bit identical, or after each difference has
  been declared in [docs/LOGIC_CHANGES.md](docs/LOGIC_CHANGES.md) under the
  fail-closed rule above. That release changes the pin and the stored
  fixtures together.
- **The contract names the python-flint actually imported.** The field
  `Contract.interval_library` is read from `flint.__version__` when the
  result is built, not copied from the pin. If python-flint has been
  replaced by hand, the result says so, and
  `test_declared_dependency_matches_the_imported_engine` fails; the
  regression tests fail only if a bit of their output changes. The field
  names the Python binding, not the FLINT C library it was built against:
  the pinned wheels fix both, a build from source may not.
- **NumPy** only carries arrays between Arb computations and is allowed a
  range (`numpy>=2.0,<3`). Continuous integration runs the suite with the
  newest NumPy in that range on every push.
- **Optional dependencies** (the `test` and `regenerate` extras) are given
  lower bounds or ranges; the package itself imports none of them.

`tests/unit/test_release.py` checks that the pin, `codemeta.json` and the
imported engine agree.

If you are unsure whether a change weakens a guarantee, say so in the pull
request: the question is welcome, and it will be answered before merging.
