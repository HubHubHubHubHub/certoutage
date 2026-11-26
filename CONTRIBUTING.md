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
6. If you used AI tools to prepare the change, say which ones and for what
   in the pull request.

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
(Python 3.10 to 3.14), macOS and Windows (Python 3.11 and 3.14). A pull
request must pass all of these jobs.

The suite includes regression tests that reproduce the archived results
**bit for bit**: floats are compared through `float.hex`, not with a
tolerance. `tests/regression/test_table_ii_example.py` runs
`examples/table_ii.py --json` and compares its output with a stored fixture.

## The fail-closed rule

certoutage returns bounds that are certified for a stated model. A change
may make a result less precise; it must never make a result less true, and
it must never do either without saying so. In practice:

- **Certifying files** are `src/certoutage/api.py`, `_runtime.py`,
  `_generate.py`, `_banks.py` and `_vendor/`. A change to any of them is
  declared in [docs/LOGIC_CHANGES.md](docs/LOGIC_CHANGES.md): what changes,
  what is preserved, and how this was checked.
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
- **Data.** A new or regenerated bank is listed in `data/MANIFEST.json` with
  its SHA-256 digest, and its license is stated in [LICENSES.md](LICENSES.md).
  The reference digest of the manifest is pinned in `_banks.py`. Queries
  never write banks and never access the network.

If you are unsure whether a change weakens a guarantee, say so in the pull
request: the question is welcome, and it will be answered before merging.
