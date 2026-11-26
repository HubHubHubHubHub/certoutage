# certoutage

[![tests](https://github.com/HubHubHubHubHub/certoutage/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/HubHubHubHubHub/certoutage/actions/workflows/tests.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24509256.svg)](https://doi.org/10.5281/zenodo.24509256)

Certified outage bounds for RIS-NOMA with source-side thermal energy harvesting

`certoutage` provides deterministic, two-sided outage bounds for the Letter's
thermal RIS-NOMA model with two users and Poisson interference. Every result
carries an explicit mathematical and numerical contract. Version **0.1.0** is
available from https://github.com/HubHubHubHubHub/certoutage.

## Installation

Python >= 3.10 is required. Install from PyPI:

```sh
python -m pip install certoutage
```

The test suite runs on every push on Ubuntu (Python 3.10 to 3.14), macOS
and Windows (Python 3.11 and 3.14), with python-flint 0.9.0.

The examples are in the repository and in the source distribution, not in
the wheel. To run them, and the tests, from a clone of the repository (on
Windows, use `.venv\Scripts\python`):

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python examples/table_ii.py
.venv/bin/python examples/new_case.py
.venv/bin/python -m pytest
```

To contribute, see [CONTRIBUTING.md](CONTRIBUTING.md).

The only runtime dependencies are **python-flint 0.9.0 and NumPy**. Normal
execution makes no network requests, does not access the original archive,
and does not write numerical banks. All banks are bundled in both the wheel
and source distribution. Calculation caches live in memory; `clear_cache()`
releases them. SciPy is optional for historical regeneration tools, through
`.[regenerate]`.

## Reference example: Table II

```python
from certoutage import Model, floor, required_snr, outage_enclosure

model = Model(N=24, lam="0.1", eta=4, convention="C-TX")
print(floor(model, 1).format(scale="1e-5"))
print(required_snr(model, 1, "1e-5").status)
p = outage_enclosure(model, 1, snr_db=5)
print(p.contract.source)
```

Expected output:

```text
[1.7136, 1.7478]
excluded
provided-banks
```

`examples/table_ii.py` reproduces the four Table II entries for C-TX,
N=24, lambda=0.1, eta=4, user 1 and target 1e-5. Floor values below are in
units of **1e-5**:

| Model or bound | Floor value | Decision | Diagnostic |
|---|---|---|---|
| Exact gain + PPP | [1.7136, 1.7478] | excluded | — |
| Exact gain + Gamma | [0.5629, 0.5757] | falsely feasible | falsely feasible |
| Eq. (3) + Gamma | [1.639, 1.668] | excluded | masked |
| E F_W(d_i J_max) | < 0.9784 | inconclusive | — |

The exact-gain/Gamma required-SNR interval is **[4.50, 4.75] dB**. The example
also prints two mean-interference comparisons in raw probability units:

```text
Exact gain + mean: {'lower': 3.716491105435498e-15, 'upper': 3.888988626422534e-15} (raw probability); falsely feasible
Eq. (3) + mean: {'lower': 9.039202781939247e-08, 'upper': 9.116853495842469e-08} (raw probability); falsely feasible
```

Use `--json` for full, unrounded results and contracts. Execution time varies.

`snr_db` means **10 log10 rho in dB**, never linear rho. `N` is the number of
RIS elements **per user** (2N in total); `user` is 1 or 2. Numerical precision
is selected per calculation with `numerics=Numerics(precision_bits=192)`;
this does not turn a supplied 160-bit bank into a 192-bit bank. Real inputs
are read through `str()`: for example, `np.float32(0.1)` selects the lambda=0.1
bank. Use a string to specify the intended decimal exactly.

## Scope

The supported model is deliberately limited:

- Exactly **eight sizes N: 8, 12, 16, 20, 24, 32, 48, 64**. Useful fading is
  Rayleigh (`m=1`) or Nakagami **m=2,3**, with elementary powers following a
  Gamma distribution of shape m and rate m.
- A planar Poisson point process outside the disk **R0=1**, with unit-mean
  exponential marks, **eta in {3,4}** and **lambda in [0,10]**. Lambda=0 gives
  the case without PPP interference. Small intensities or a coarse
  discretization can yield wide bounds and an `inconclusive` decision.
- Thermal source `(10+Z)^2/101`, with standard normal Z; ideal alignment,
  independent amplitudes, no direct path, and fixed NOMA and useful-link
  parameters: p1=0.3, p2=0.7, theta=1, ell1=1/8, ell2=1/64,
  d1=80/3 and d2=160.
- Two power conventions: **C-INR**, E F_W(d_i(1+J)/rho), and **C-TX**,
  E F_W(d_i(J+1/rho)). The C-INR floor is zero; the C-TX floor is evaluated
  at 1/rho=0.
- Propagated Chernoff bounds for Rayleigh N=20,24 with PPP interference,
  and also N=8,64 without PPP interference. These give **sufficient designs**,
  not impossibility proofs.

Arbitrary N, arbitrary real m, other eta, variable R0, Rice fading, 3GPP
channels, correlation, phase errors and RIS without thermal harvesting are
not implemented. Unsupported inputs raise an explicit error (`ValueError`
for unsupported model parameters). This is **not `inconclusive`** and no
unsupported value is rounded to a supported case.

Certificates are **two-sided bounds for the specified model**, conditional
on its mathematical assumptions, the Arb/Acb arithmetic engine, the archive's
analytical bounds and bank integrity. They do not guarantee physical-model
validity, packet latency, a universal relative width or a maximum computation
time. Higher precision does not repair an unsuitable physical model.

## What is computed and what is supplied

`result.contract.source` distinguishes:

| Source | Meaning |
|---|---|
| `provided-banks` | Composition computed on demand from integrity-checked signal and interference banks |
| `mixed` | Supplied useful-gain bank; PPP, Gamma or J_max distribution computed locally for the requested case |
| `provided-certificate` | Final J_max bounds for N=20/24 read from archived certificates, explicitly without a new integration |
| `analytic` | An exact result such as the zero C-INR floor |

Bank contents and the manifest are checked with SHA-256 **before loading**.
The manifest's reference digest is pinned in the code. A mismatch raises
`IntegrityError` and stops the calculation using that data; it never becomes
an `inconclusive` result. A bank already loaded is reused from memory; every
new read verifies it again. SHA-256 checks **integrity against a reference
digest**, not provenance or mathematical correctness. A purely analytical
result that uses no bank does not depend on bank contents.

For lambda=0.1 or 1 and eta=3 or 4, supplied PPP/Gamma banks are used. For a
new lambda, the PPP inversion is computed on demand with Fourier, aliasing
and tail remainder bounds; the default is M=2^18. The useful-gain bank is
still supplied: this is not full regeneration of the case. The contract
records bank filenames, SHA-256 digests, parameters and precision.

## Decisions and approximations

`required_snr(model, user, target, grid=SNRGrid())` returns `feasible` (a
threshold enclosed by certified grid points), `excluded` (a floor lower bound
strictly above the target), or `inconclusive`. The default grid is [-40,96] dB
with step 1/16. Left censoring uses -infinity as the threshold's lower bound;
exhausting the grid never proves exclusion at every SNR.

**Approximations are non-certified substitutes for the exact PPP outage.**
`compare_approximations(model, user, target)` reports exact gain + PPP,
exact gain + **moment-matched Gamma-distributed interference**, **Eq. (3)** +
Gamma, two mean-interference comparisons and the **largest-interferer bound**.
Intervals rigorously enclose the comparator models; they do not by themselves
bound the exact PPP outage or certify the substitution error. The
`falsely feasible` and `masked` diagnostics follow decision rules, not
recognition of a predefined example.

The J_max result is a **floor lower bound**. Its upper endpoint below the
target remains `inconclusive`. In Table II, only the exact PPP floor proves
impossibility within the PPP model. `masked` explains why exclusion under
Eq. (3) + Gamma does not validate replacing PPP interference by Gamma.

[Detailed API](docs/API.md) · [Mathematical contract](docs/CONTRACT.md) ·
[Register of guarantees](docs/GUARANTEES.md) ·
[Regeneration](docs/REGENERATION.md) · [Logic changes](docs/LOGIC_CHANGES.md) ·
[Extraction inventory](docs/EXTRACTION.md).

## Provenance

The results in Victor Rabiet's *Certified Outage Bounds for RIS-Assisted NOMA
with Source-Side Thermal Energy Harvesting* were produced by the
[reproducibility archive](https://doi.org/10.5281/zenodo.24450534) (archive v7,
metadata version 1.1). The Letter is [available on HAL](https://hal.science/hal-05879102),
submitted to IEEE Wireless Communications Letters.

`certoutage` is a **subsequent extraction, dated 24 November 2026**. It
reproduces Table II identically, as verified against the archived reference
results, but it was not the software used to produce the submitted results.
The original archive remains read-only. Banks are copied byte for byte or
repacked without loss; code changes are documented file by file. The archive
DOI identifies the original reproducibility archive, not this software.

## Citation

See [CITATION.cff](CITATION.cff) and [codemeta.json](codemeta.json). Cite this
extraction as:

> Victor Rabiet (2026). certoutage: certified outage bounds for thermal
> RIS-NOMA. Version 0.1.0, 24 November 2026. https://doi.org/10.5281/zenodo.24509257

Also acknowledge the original [archive](https://doi.org/10.5281/zenodo.24450534)
and the [Letter](https://hal.science/hal-05879102). Software DOI: [10.5281/zenodo.24509256](https://doi.org/10.5281/zenodo.24509256)
(all versions); version 0.1.0 is [10.5281/zenodo.24509257](https://doi.org/10.5281/zenodo.24509257).

## Licenses

The distribution uses **BSD-3-Clause AND MIT AND CC-BY-4.0**. New author code
is under [BSD-3-Clause](LICENSE), Copyright (c) 2026 Victor Rabiet. Extracted
code retains its MIT notice; numerical banks and regression data retain
CC BY 4.0. [LICENSES.md](LICENSES.md) maps files to licenses, attribution and
modifications. The [original archive notice](docs/ARCHIVE_LICENSE.txt) and
[full CC BY 4.0 terms](docs/CC-BY-4.0.txt) are included in both distributions.

## Roadmap — not implemented

Possible future extensions are RIS without thermal harvesting, Rice fading
and 3GPP channel models. None is implemented or certified in version 0.1.0.

## Support, bugs and feature requests

If your work needs a feature that is not implemented yet, please
[open a feature request](https://github.com/HubHubHubHubHub/certoutage/issues/new/choose)
and say what it is for. If it can be done in a reasonable time, it will be
implemented and you will be notified on the issue when it is released. Bug
reports, questions and other feedback go to the same tracker; see
[SUPPORT.md](SUPPORT.md). To propose a change, see
[CONTRIBUTING.md](CONTRIBUTING.md). Collaborations are welcome: for them, or for a
private message, use the e-mail address given in the author's papers on
[HAL](https://hal.science/search/index?q=authIdHal_s:victor-rabiet), for
instance the [Letter](https://hal.science/hal-05879102).
