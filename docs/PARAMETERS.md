# Model parameters: fixed, free and planned

This page lists every parameter of the model of the Letter. For each one, it says whether the parameter is fixed or free in
the current version, which version is planned to free it, and what must hold before it is freed. Planned items are **not
implemented**. Until a version frees a parameter, any other value raises `ValueError`, as described in the README.

Notation: d_i = c_i/ℓ_i is the decoding constant of user i divided by its useful path gain. In the Letter, d1 = 80/3 and
d2 = 160. Distances are measured in units of the guard radius R0, and the interference path gain equals one at R0.

| Parameter | Letter value | Current version (0.2.0 and `main`) | Planned | What must hold first |
|---|---|---|---|---|
| Target outage probability p* | 10⁻³ to 10⁻⁵ | free | — | — |
| SNR grid | [−40, 96] dB, step 1/16 dB | free (multiples of 1/128 dB) | — | — |
| Power convention | C-TX, C-INR | free | — | — |
| Interference intensity λ (mean number of interferers per area R0², since lengths are in units of R0) | 0.1, 1 | free in [0, 10]; banks for 0.1 and 1, otherwise computed on demand | — | — |
| Precision, PPP DFT size, bank policy | 160 bits, 2¹⁸ or 2²⁰ | free | — | — |
| Power fractions p1, p2; decoding threshold θ (or one threshold per user); useful path gains ℓ1, ℓ2 | 0.3, 0.7; 1; 1/8, 1/64 | fixed | 0.3.0 | these enter only through d_i; validation of p2 − θp1 > 0 |
| d_i (one per user) | 80/3, 160 | fixed | 0.3.0 | monotonicity of F_W, so that the conservative bank lookup stays valid for a rescaled argument; one argument per call, never stored in a cached object; outside the range of a bank, the bounds become trivial (0 or 1), which is valid but uninformative; narrower usable range for Nakagami m = 2, 3 |
| Interference gain g at the guard distance (in C-INR, the interference-to-noise ratio of a unit-mark interferer at R0) | 1 | fixed | 0.3.0 | scaling identity of the PPP; g applied once, to the PPP, Gamma, mean and largest-interferer distributions alike. `R0` itself stays 1: it sets the unit of length |
| Interference path-loss exponent η | 3, 4 | 3 or 4 (explicit transforms) | 0.3.0, as a real number in an announced domain | written statement and proof of the transform for real η > 2 and of the Fourier remainder bound; an independent check of the general transform; η read as an exact decimal; announced domain jointly in (λ, η, DFT size) |
| Thermal mean and standard deviation | 10, 1 | fixed | 0.4.0 | new signal banks, computed from the useful-gain banks; correct treatment of the thermal cell that contains the zero of the thermal factor |
| Number of RIS elements per user N | 8, 12, 16, 20, 24, 32, 48, 64 | these eight sizes | 0.4.0 | bank generation on demand, with the same contract as the eight archived sizes |
| Nakagami parameter m | 1, 2, 3 | 1, 2, 3 | not planned | no certified routine for real m |
| Distribution of the interferer marks | Exp(1) | fixed | 1.1.0 or later (generic Poisson-interference kernel) | a new transform and a new Fourier bound |
| Constants of the inversions (PPP period and damping, useful-gain DFT) | as in the Letter | fixed | not planned for users | — |

The Letter's values remain the defaults of every planned version, and all archive regressions must stay unchanged.
