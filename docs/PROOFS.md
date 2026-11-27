# Proofs for the general interface (unreleased 0.3.0)

**Status: provisional proof.** These proofs are stated as they are used by
the package. They will become definitive after a formalization in Lean and
a final human reading. Until then, the guarantees that rest on them are
conditional on them, in the same way as on the analytic proofs of the
Letter ([CONTRACT.md](CONTRACT.md), last section).

This document covers what the 0.3.0 contract cannot refer to the Letter
for: the free link coefficients and interference gain (§ 1), the Laplace
transform of the interference for real η (§ 2), the Fourier bound, the
remainder R and the tail bound τ for every η > 2 (§ 3), the informative
domain D_M (§ 4) and the cumulants of J (§ 5). § 6 says, statement by
statement, which test checks it, whether the reference values of that test
come from outside the package, and which statements have no test of their
own.

## 0. Setting and notation

Π is a planar Poisson point process of intensity λ ≥ 0 outside the unit
disk. The marks H_x are i.i.d. Exp(1), independent of the positions, and

  J = Σ_{x∈Π} H_x |x|^(−η),  η > 2,  α = 2/η ∈ (0, 1).

F_W is the CDF of the useful-signal statistic W = A_N²(10+Z)²/101 of the
contract; only its monotonicity is used below (F_W is nondecreasing,
F_W(0) = 0). For d ≥ 0, g ≥ 0 and ρ > 0,

  P_INR(ρ; d, g) = E F_W(d(1 + gJ)/ρ),  P_TX(ρ; d, g) = E F_W(d(gJ + 1/ρ)).

Branches of powers and logarithms are principal. B > 0 and c > 0 are the
period and the damping of the Fourier inversion (the package uses B = 128,
cB = 20), K ≥ 1 is an integer and M = 2K is the DFT size.

## 1. Link coefficients and interference gain

**Proposition 1.1 (monotonicity in d).** Let J ≥ 0 be finite and F a
nondecreasing measurable function with values in [0, 1]. For ρ > 0, the maps
d ↦ E F(d(1+J)/ρ) and d ↦ E F(d(J + 1/ρ)) are nondecreasing on [0, ∞).

*Proof.* The arguments are almost surely ordered in d; take expectations. ∎

Whether d is rational plays no part in the mathematics; it is used only for
exact validation in the code.

**Proposition 1.2 (bank lookup and extension).** Let H(t) = F_W(d⋆t) with
d⋆ ≥ 0, and let 0 < t_1 < … < t_n be nodes with L_j ≤ H(t_j) ≤ U_j and
0 ≤ L_j ≤ U_j ≤ 1. Define

  L_B(t) = max({0} ∪ {L_j : t_j ≤ t}),  U_B(t) = min({1} ∪ {U_j : t_j ≥ t}).

Then L_B(t) ≤ H(t) ≤ U_B(t) for every t ≥ 0. If 0 ≤ t⁻ ≤ ry ≤ t⁺, then
L_B(t⁻) ≤ F_W(d⋆ r y) ≤ U_B(t⁺).

*Proof.* If t_j ≤ t, then L_j ≤ H(t_j) ≤ H(t); if t_j ≥ t, then
H(t) ≤ H(t_j) ≤ U_j; 0 and 1 are universal bounds. The second claim
follows from the monotonicity of L_B, U_B and H. ∎

In particular, below the range of the bank the enclosure is [0, min_j U_j]
and above it [max_j L_j, 1]. Freezing both bounds at the values of the
extreme node would be wrong. This is the rule "below its range the lower
bound is 0; above it the upper bound is 1" of [API.md](API.md#model-and-calculation).

**Proposition 1.3 (two-threshold SIC).** Let p_1, p_2, θ_1, θ_2 > 0. User 1
decodes when p_2S/(p_1S + V) ≥ θ_2 and p_1S/V ≥ θ_1, where S ≥ 0 is the
useful power before allocation and V > 0 is noise plus interference. If
p_2 − θ_2p_1 > 0, this is S/V ≥ c_1, and user 2 decodes when S/V ≥ c_2, with

  c_1 = max{θ_1/p_1, θ_2/(p_2 − θ_2p_1)},  c_2 = θ_2/(p_2 − θ_2p_1).

If p_2 − θ_2p_1 ≤ 0, the condition (p_2 − θ_2p_1)S ≥ θ_2V > 0 is
impossible, and both outage probabilities are exactly 1.

*Proof.* The first condition is (p_2 − θ_2p_1)S ≥ θ_2V; divide by the
positive factor when it is positive. The second condition is S/V ≥ θ_1/p_1. ∎

This is why `Model.from_link` tests the sign of p_2 − θ_2p_1 before any
division.

**Proposition 1.4 (transport of the guard radius).** For R_0 > 0, λ′ > 0 and
any law of nonnegative marks, J_{λ′,R_0} has the same law as
R_0^(−η) J_{λ′R_0²,1}, as variables with values in [0, ∞].

*Proof.* The map x ↦ x/R_0 sends a Poisson process of intensity λ′ outside
the disk of radius R_0 to a Poisson process of intensity λ′R_0² outside the
unit disk (mapping theorem; G. Last and M. Penrose, *Lectures on the Poisson
Process*, Cambridge University Press, 2017, Thms 5.1 and 5.6); the marks are
unchanged, and |x|^(−η) = R_0^(−η)|y|^(−η). ∎

**Corollary 1.5 (normalization).** Let the physical interference be
I = P_I κ Σ_x H_x |x|^(−η), and ρ = P/N_0. If P_I does not depend on P
(C-INR), then λ = λ′R_0², g_INR = P_I κ R_0^(−η)/N_0, and the outage is
P_INR(ρ; d, g_INR). If P_I = aP with a ≥ 0 fixed (C-TX), then
g_TX = aκR_0^(−η), without N_0, and the outage is P_TX(ρ; d, g_TX). The
probabilities depend on (λ′, R_0, κ) only through λ′R_0² and κR_0^(−η) (and
the power factor): for every ν > 0, (λ′, R_0, κ) ↦ (λ′/ν², νR_0, ν^η κ)
preserves them, and the physical triple is not identifiable.

*Proof.* Proposition 1.4, then substitution in the decoding conditions. ∎

**Proposition 1.6 (monotonicity in g, and g = 0).** Let φ be nondecreasing
and bounded, and a, g ≥ 0. The test function x ↦ φ(a + gx) is
nondecreasing on [0, ∞). It is extended at +∞ by φ(+∞) if g > 0 and by φ(a)
if g = 0 (convention 0·∞ = 0). Hence, if X⁻ ≤_st J ≤_st X⁺ are the two
discrete laws of the contract (residual mass at +∞ for X⁺), then
E φ(a + gX⁻) ≤ E φ(a + gJ) ≤ E φ(a + gX⁺) for every g ≥ 0. At g = 0,
P_INR(ρ; d, 0) = P_TX(ρ; d, 0) = F_W(d/ρ) exactly, and the residual mass at
+∞ must receive F_W(d/ρ), not 1. Both probabilities are nondecreasing in g.

*Proof.* A nondecreasing test function preserves stochastic order. The
extension at +∞ is the limit of φ(a + gx) as x → ∞. Monotonicity in g holds
pointwise because J ≥ 0. ∎

The package applies g = 0 as the case without interference, which is the
exact value given by Proposition 1.6.

**Proposition 1.7 (scaling identities).** For d, ρ, r > 0,
P_INR(ρ; d, g) = P_INR(ρ/r; d/r, g); with d_2 = 6d_1 this is
P_2(6ρ) = P_1(ρ) in C-INR. For g > 0, P_TX(ρ; d, g) = P_TX(ρg; dg, 1).
In C-TX, P_TX(ρ/r; d/r, g) = E F_W(dgJ/r + d/ρ). If g > 0, d > 0,
Pr(J > 0) > 0 and F_W is strictly increasing on [0, ∞) (as for the W of the
contract), this is strictly smaller than P_TX(ρ; d, g) for r > 1 and
strictly larger for r < 1. There is no scaling identity in d alone in C-TX
when interference is present; at g = 0 both sides equal F_W(d/ρ).

*Proof.* The arguments agree: d(1+gJ)/ρ = (d/r)(1+gJ)/(ρ/r), and
d(gJ + 1/ρ) = dg(J + 1/(ρg)). For the C-TX inequality, the argument
decreases strictly on {J > 0} when r > 1. ∎

## 2. Laplace transform of J for real η

For Re s ≥ 0, the exponential formula for marked Poisson processes (licit
because |1 − e^(−sy)| ≤ |s|y for y ≥ 0, and E J < ∞), applied with
independent Exp(1) marks, gives

  L_J(s) = E e^(−sJ) = exp(−2πλ 𝒥(s)),  𝒥(s) = ∫_1^∞ s r/(r^η + s) dr.

Write F_b(z) = ₂F₁(1, b; b+1; z) = Σ_{n≥0} b z^n/(b + n) for 0 < b < 1.

**Proposition 2.1 (first identity).** On Ω_1 = ℂ ∖ (−∞, −1], 𝒥 is
holomorphic and

  𝒥(s) = s/(η − 2) · ₂F₁(1, 1 − α; 2 − α; −s),  s ∈ Ω_1 (including s = 0).

*Proof.* Holomorphy: on compact subsets of Ω_1, r^η + s does not vanish
and the integrand is bounded by C r^(1−η) at infinity. With u = r^(−η),
𝒥(s) = (s/η) ∫_0^1 u^(−α)/(1 + su) du. For b > 0 and z ∉ [1, ∞),
F_b(z) = b ∫_0^1 u^(b−1)/(1 − zu) du (geometric series for |z| < 1, then
analytic continuation; DLMF 15.6.1). Take b = 1 − α and z = −s; then
s/η · 1/(1−α) = s/(η − 2). ∎

**Proposition 2.2 (second identity).** On Ω_2 = ℂ ∖ (−∞, 0],

  𝒥(s) = π s^α/(η sin πα) − ½ ₂F₁(1, α; 1 + α; −1/s).

*Proof.* For s > 0, r = s^(1/η)u gives ∫_0^∞ sr/(r^η + s) dr
= s^α ∫_0^∞ u/(1 + u^η) du = π s^α/(η sin πα) (Beta integral, 0 < α < 1),
extended to Ω_2 by holomorphy and the identity theorem. With u = r^η,
∫_0^1 sr/(r^η + s) dr = (1/η) ∫_0^1 u^(α−1)/(1 + u/s) du = ½ F_α(−1/s). ∎

Both identities therefore hold on the whole half-plane Re s > 0. The package
chooses between them by the midpoint of |s|: this choice is numerical only.
On Ω_1 ∖ Ω_2 the two terms of Proposition 2.2 would have to be continued
jointly; they are never evaluated there.

**Proposition 2.3 (unit circle and Pfaff fallback).** On |z| = 1, z ≠ 1,
the series of F_b converges (Dirichlet test), not absolutely; it diverges at
z = 1 only (the logarithmic case c − a − b = 0, DLMF § 15.2(i)). Pfaff's
transformation (DLMF 15.8.1) gives F_b(z) = (1 − z)^(−1) ₂F₁(1, 1; b+1; q),
q = z/(z − 1). With Proposition 2.1 for |s| ≤ 1 and Proposition 2.2 for
|s| ≥ 1, Re s ≥ 0, the argument z satisfies |z| ≤ 1 and Re z ≤ 0, hence

  |q|² = |z|²/(1 + |z|² − 2 Re z) ≤ ½.

The terms T_n = n! q^n/(b+1)_n satisfy |T_{n+1}/T_n| ≤ |q|, so
|Σ_{n≥N} T_n| ≤ |T_N|/(1 − |q|).

*Proof.* (n+1)/(b+1+n) ≤ 1 for b > 0 gives the ratio bound; sum the
geometric majorant. For the bound on |q|: |z − 1|² = 1 + |z|² − 2 Re z
≥ 1 + |z|² ≥ 2|z|² when |z| ≤ 1. ∎

**Explicit exponents.** For η = 4, 𝒥(s) = (√s/2) arctan √s. For η = 3 and
q = s^(1/3),
𝒥(s) = q²[⅓ Log(1+q) − ⅙ Log(1 − q + q²) + (1/√3)(arctan((2q−1)/√3) + π/6)],
from 𝒥(s) = q² ∫_0^q du/(1 + u³). The principal branches are valid on
Re s > 0. The package keeps the expressions of the archive at η = 3 and 4.
For η = 4 it is the one above; for η = 3 the archive writes the same function
in t = 1/q = s^(−1/3):
𝒥(s) = s^(2/3)[π/(2√3) + ⅓ Log(1+t) − ⅙ Log(t² − t + 1) − (1/√3) arctan((2t−1)/√3)],
which agrees with the form above on Re s > 0.

**Rigorous evaluation.** Arb evaluates ₂F₁ with rigorous error bounds
(F. Johansson, “Computing hypergeometric functions rigorously”, *ACM Trans.
Math. Softw.* 45(3), article 30, 2019, doi:10.1145/3328732). Balls for a, b
and c do not by themselves prove the exact relation a + b − c = 0; it holds
by construction here and is declared with `abc=True`. A rigorous output can
still be wide: the package checks finiteness and width at each call, doubles
the precision once, then uses the Pfaff series of Proposition 2.3.

## 3. Fourier bound, remainder R and tail τ, for every η > 2

Let β = π²λα/[2 sin(πα/2)], z_k = c + iω_k and ω_k = 2πk/B.

**Statement A (Fourier majorant).** For every η > 2, λ ≥ 0, c > 0 and real t,

  |L_J(c + it)| ≤ exp(πλ − β|t|^α).

*Proof.* |L_J(s)| = exp(−2πλ Re 𝒥(s)) and 𝒥 = 𝒥_plane − 𝒥_disk, with
𝒥_plane(s) = ∫_0^∞ sr/(r^η + s) dr and 𝒥_disk(s) = ∫_0^1 r/(1 + r^η/s) dr,
both absolutely convergent for Re s > 0.
(1) As in Proposition 2.2, 𝒥_plane(s) = π s^α/(η sin πα) on Re s > 0 (on a
compact set where Re s ≥ δ > 0 and |s| ≤ C, the integrand is bounded by
Cr/δ for r ≤ 1 and by Cr^(1−η) for r ≥ 1; the identity theorem extends the
real-axis value).
(2) Re(1/s) > 0, so w = r^η/s has Re w ≥ 0 and
0 ≤ Re[1/(1+w)] = (1 + Re w)/|1 + w|² ≤ 1/(1 + Re w) ≤ 1; hence
0 ≤ Re 𝒥_disk ≤ ½.
(3) For s = c + it, |arg s| < π/2, so cos(α arg s) ≥ cos(πα/2) > 0, and
|s| ≥ |t|. With sin πα = 2 sin(πα/2) cos(πα/2),
Re 𝒥_plane(s) ≥ π|t|^α/(2η sin(πα/2)), including t = 0 and t < 0.
(4) log |L_J| ≤ −π²λ|t|^α/(η sin(πα/2)) + πλ = πλ − β|t|^α, since 1/η = α/2. ∎

For fixed c > 0, log |L_J(c + it)| + β|t|^α → πλ as |t| → ∞: no smaller
constant is uniform with this β.

**Lemma B0 (pointwise Fourier identity).** Let λ > 0.
(i) F_J is continuous and F_J(0) = 0. The process has almost surely at
least one point; condition on all positions and on all marks except that of
the point nearest to the origin (unique almost surely). Its contribution is a
positive multiple of an independent exponential variable, so the
conditional law of J has no atom, and neither has the law of J.
(ii) Let h(u) = e^(−cu)F_J(u) for u ≥ 0 and h(u) = 0 for u < 0, and let
Q(x) = Σ_{ℓ∈ℤ} h(x + ℓB). Q is B-periodic and continuous (uniform
convergence on [0, B], the terms ℓ ≥ 0 being dominated by e^(−cℓB)). For
0 < x < B, Q(x) = e^(−cx)S(x), with S(x) = Σ_{ℓ≥0} e^(−cℓB)F_J(x + ℓB).
(iii) By Fubini, Q̂(k) = (1/B)∫_0^∞ e^(−z_k u)F_J(u) du = L_J(z_k)/(Bz_k),
because ∫_0^∞ e^(−su) Pr(J ≤ u) du = L_J(s)/s for Re s > 0 (absolute
integrability: ∫_0^∞ e^(−cu)F_J(u) du ≤ 1/c). By Statement A,
|Q̂(k)| ≤ C e^(−a|k|^α)/|k| for k ≠ 0, with a = β(2π/B)^α > 0. The Fourier
series converges absolutely and uniformly; two continuous functions with the
same coefficients have equal Fejér means, which converge uniformly, so for
0 < x < B and at every point,

  S(x) = (e^(cx)/B) Σ_{k∈ℤ} [L_J(z_k)/z_k] e^(iω_k x). ∎

**Statement B (truncation remainder).** Let v_k = L_J(z_k)/z_k (so
v_(−k) = conj(v_k), v_0 real) and the truncation with half weight at rank K,

  T_K(x) = (e^(cx)/B)[v_0 + Σ_{k=1}^{K−1}(v_k e^(iω_k x) + conj(v_k) e^(−iω_k x))
           + ½(v_K e^(iω_K x) + conj(v_K) e^(−iω_K x))].

With ξ = β(2πK/B)^α, for 0 < x < B,

  |S(x) − T_K(x)| ≤ e^(cx) R,  R = (e^(πλ−ξ)/π)(1/(2K) + 1/(αξ)).

*Proof.* By Lemma B0, S − T_K is the sum of the omitted terms. For k ≥ 1,
|v_k| ≤ (B/(2πk)) e^(πλ − a k^α) by Statement A, and ξ = aK^α. The omitted
half pair at ±K costs at most e^(cx)|v_K|/B ≤ e^(cx) e^(πλ−ξ)/(2πK). The
pairs |k| > K cost at most (e^(cx)e^(πλ)/π) Σ_{k>K} f(k), with
f(u) = e^(−au^α)/u. Since f′(u) = −e^(−au^α)(1 + aαu^α)/u² < 0,
f(k) ≤ f(u) on [k−1, k], so
Σ_{k>K} f(k) ≤ ∫_K^∞ f = E_1(ξ)/α ≤ e^(−ξ)/(αξ), for every ξ > 0. Add. ∎

The proof uses only Statement A. It therefore holds for any nonnegative
variable Y with continuous CDF, F_Y(0) = 0 and
|L_Y(c + it)| ≤ A e^(−b|t|^α) for all real t (A, b, α > 0), with
R = (A e^(−ξ)/π)(1/(2K) + 1/(αξ)) and ξ = b(2πK/B)^α. For J: A = e^(πλ),
b = β.

**Identification with the computation.** At the nodes x_j = jB/M,
e^(±iω_K x_j) = (−1)^j, so the half pair equals Re(v_K)(−1)^j. If
IFFT(V)_j = (1/M) Σ_{k=0}^{M−1} V_k e^(2πijk/M), with V_0 = v_0, V_k = v_k and
V_(M−k) = conj(v_k) for 0 < k < K, and V_K = Re(v_K), then
T_K(x_j) = (M/B) e^(cx_j) IFFT(V)_j. This is the real DFT of size M with
Nyquist coefficient Re(v_K). The identification holds **at the nodes
only**: off the grid T_K also contains −Im(v_K) sin(ω_K x). The package
does not interpolate.

**Statement C (tail).** μ_J = E J = 2πλ/(η − 2) and

  Pr(J > B) ≤ τ = exp(−B/2 + μ_J).

*Proof.* For 0 ≤ θ < 1 and r ≥ 1, E e^(θH r^(−η)) = 1/(1 − θr^(−η)) and
0 ≤ (E e^(θH r^(−η)) − 1) r = θr/(r^η − θ) ≤ (θ/(1−θ)) r^(1−η), which is
integrable on [1, ∞). Apply the exponential formula to
J_T = Σ_{1<|x|≤T} H_x|x|^(−η) and let T → ∞ by monotone convergence. At
θ = ½: log E e^(J/2) = 2πλ ∫_1^∞ r/(2r^η − 1) dr ≤ 2πλ ∫_1^∞ r^(1−η) dr = μ_J,
because 2r^η − 1 ≥ r^η. Markov's inequality applied to e^(J/2) concludes. ∎

τ may exceed 1; the bound is then uninformative, not wrong (τ may be
replaced by min(1, τ)). The exponential moment is finite exactly for θ < 1.

**Certificate at the nodes.** Let q = e^(−cB) and a_0 = q/(1 − q)
= 1/expm1(cB). For 0 < x < B,
S(x) = F_J(x) + a_0 − Σ_{ℓ≥1} q^ℓ Pr(J > x + ℓB), and the last sum lies in
[0, τa_0] by Statement C. With Statement B,

  T_K(x) − a_0 − e^(cx)R ≤ F_J(x) ≤ T_K(x) − a_0 + e^(cx)R + τa_0.

At x = 0 the package imposes F_J(0) = 0 (Lemma B0 (i)). At x = B,
Statement C gives max(0, 1 − τ) ≤ F_J(B) ≤ 1. If R > 1, the package does not
use the DFT: it returns the trivial bounds [0, 1] at the interior nodes, with
[max(0, 1 − τ), 1] at B. This is the certificate quoted in
[CONTRACT.md](CONTRACT.md#on-demand-ppp-inversion), which also describes how
the stored bound at B is selected after the conservative index choice.

**Scope.** Statements A, B and C, Lemma B0 and the certificate hold for every
η > 2, λ > 0, c > 0, B > 0 and integer K ≥ 1, with no condition on ξ or M.

## 4. The informative domain D_M

Let Ω = πM/B, A(α, M) = π²α Ω^α/[2 sin(πα/2)] and ξ = λA (the ξ of
Statement B with K = M/2). Then

  R = (e^((π−A)λ)/π)(1/M + 1/(αAλ)).

**Proposition 4.1 (λ).** ∂_λ log R = π − A − 1/[λ(1 + αAλ/M)]. R is strictly
decreasing on λ > 0 if and only if A ≥ π. If A < π, R decreases, then
increases, with a unique minimum.

*Proof.* Differentiate. If A ≥ π the derivative is negative. If A < π it
tends to −∞ as λ → 0 and to π − A > 0 as λ → ∞, and the last term is
monotone in λ. ∎

**Proposition 4.2 (M).** R is strictly decreasing in M, tends to +∞ as
M ↓ 0 and to 0 as M → ∞.

*Proof.* A increases with M; each factor of R decreases. ∎

**Proposition 4.3 (η).** Let L = ∂_α log A = log Ω + 1/α − (π/2)cot(πα/2).
Then ∂_η log R = (2/η²)[ξL + (1/α + L)/(1 + αξ/M)]. If Ω ≥ 1, then L > 0,
A > π, and R is strictly increasing in η.

*Proof.* dα/dη = −2/η² and the chain rule give the derivative. With
u = πα/2 ∈ (0, π/2), 1/α − (π/2)cot(πα/2) = (π/2)(1/u − cot u) > 0 because
tan u > u; with log Ω ≥ 0, L > 0. Also A ≥ π · u/sin u > π. ∎

Without Ω ≥ 1 there is no universal monotonicity: at B = 128, M = 2, η = 4,
L < −2 and ∂_η R < 0. For B = 128, Ω ≥ 1 holds for M ≥ 41; every grid size
of the package (M = 2^12 to 2^20) satisfies it.

**Proposition 4.4 (τ).** τ increases with λ, decreases with η and does not
depend on M. With C_τ = B/2 + log ε_τ: if C_τ ≤ 0 the set {λ > 0 : τ ≤ ε_τ}
is empty; otherwise τ ≤ ε_τ if and only if λ ≤ λ_τ(η) = C_τ(η − 2)/(2π).

**Proposition 4.5 (domain).** Let cB = 20 and r_0 = ε_R e^(−20). If Ω ≥ 1,
then for every η > 2 there is a unique λ_R(η, M) with R(λ_R, η, M) = r_0;
λ_R increases with η and decreases with M, and

  D_M = {(λ, η) : η > 2, λ_R(η, M) ≤ λ ≤ λ_τ(η)}.

*Proof.* By Propositions 4.1 and 4.3, R is continuous and strictly
decreasing in λ, with R → +∞ as λ → 0 and R → 0 as λ → ∞, so the root is
unique. Its monotonicity follows from Propositions 4.2 and 4.3 and the
implicit function theorem. Proposition 4.4 gives the upper boundary. ∎

The package brackets λ_R by bisection with certified signs.

**Proposition 4.6 (what "informative" bounds).** On D_M the analytic width
of the certificate of § 3 at every node is at most 2ε_R + a_0ε_τ (because
cx ≤ cB = 20). The criteria bound neither the monotone discretization, nor
the width of the useful-gain banks, nor evaluation errors. With
ε_R = 10⁻⁷ and ε_τ = 10⁻¹⁰: r_0 ≈ 2.06·10⁻¹⁶, C_τ ≈ 40.974 and
λ_τ(η) ≈ 6.521(η − 2).

Outside D_M the certificate remains valid; it may be wide. When λ = 0 or
g = 0 no inversion contributes, and the domain does not apply.

**Proposition 4.7 (trivial regime).** The aliasing term satisfies τa_0 ≥ 1
if and only if μ_J = 2πλ/(η − 2) ≥ B/2 + log expm1(cB), that is, for B = 128
and cB = 20, λ ≥ λ_triv(η) = (64 + log expm1(20))(η − 2)/(2π)
≈ 13.369(η − 2). Then every interior node of the certificate of § 3 has
width at least 1, and the lower bound at B, max(0, 1 − τ), is 0.

*Proof.* τa_0 = exp(−B/2 + μ_J)/expm1(cB); take logarithms. The width at an
interior node is 2e^(cx)R + τa_0 ≥ τa_0, and τ ≥ expm1(20) > 1. ∎

Below λ_triv the term τa_0 still adds to the width: it is at most
1.7·10⁻¹⁰ for λ ≤ 1.5λ_τ, about 2·10⁻³ at 1.9λ_τ, and λ_triv ≈ 2.05λ_τ.
Since λ_triv ≥ 10 exactly when η ≥ 2.748, the trivial regime meets the
accepted λ ∈ [0, 10] only for η < 2.748. The remedy would be a window B
adapted to μ_J; the package keeps B = 128.

## 5. Cumulants of J and the Gamma comparator

For |t| < 1,
log E e^(tJ) = 2πλ ∫_1^∞ (1/(1 − tr^(−η)) − 1) r dr = 2πλ Σ_{j≥1} t^j/(jη − 2)
(termwise integration is licit since Σ |t|^j/(jη − 2) < ∞), hence

  κ_j = 2πλ j!/(jη − 2),  μ_J = κ_1 = 2πλ/(η − 2),  σ_J² = κ_2 = 2πλ/(η − 1).

For η ≤ 2, J = ∞ almost surely. The moment-matched Gamma comparator has
shape κ_1²/κ_2 = 2πλ(η − 1)/(η − 2)² and scale κ_2/κ_1 = (η − 2)/(η − 1);
for gJ, the same shape and scale multiplied by g. This comparator is not a
bound on the PPP outage ([CONTRACT.md](CONTRACT.md#on-demand-ppp-inversion)).

## 6. Tests of these statements

Register row G63 in [GUARANTEES.md](GUARANTEES.md). Tests are in
`tests/unit/`. "Independent" means that the reference values of the test do
not come from the code of the package that the statement justifies. A
numerical test checks finitely many cases; it does not replace the proof.

**Independent tests.**

| Statement | Test and what it checks |
|---|---|
| Propositions 2.1, 2.2 | `test_real_eta.py::test_general_matches_independent_integral` (η from 2.5 to 8) and `::test_general_matches_independent_integral_near_two` (η = 2.1 to 2.25): Acb quadrature of 𝒥 by two other substitutions, against the package's 2F1 path |
| Proposition 2.3 | `test_real_eta.py::test_pfaff_truncated_series_contains_reference`: truncated Pfaff series and remainder against Arb's 2F1 |
| Statement A | `test_proofs.py::test_statement_a_majorant`: Re 𝒥(c+it) by quadrature, η from 2.1 to 8, c = 0.001, 20/128 (the package's value) and 3, t up to 10⁴ in absolute value |
| Statement B | `test_proofs.py::test_statement_b_on_a_known_distribution`: the general form, on the Lévy distribution, whose CDF and transform are explicit; the bound is nearly attained at the first node. On this distribution the bound also holds with weight 0 or 1 at rank K, so this test does not check the half-weight convention |
| Identification with the computation | `test_proofs.py::test_dft_identification_at_the_nodes`: inverse DFT with V_K = Re(v_K) against the direct half-weight sum, at every node; a full weight is detected |
| Statement C (integral inequality) and § 5 (series of the cumulant function at t = ½) | `test_proofs.py::test_statement_c_and_cumulants`: quadrature against 1/(η − 2) and against the series. The exponential formula and Markov's step are not checked numerically |
| Propositions 4.1, 4.3 (derivatives, signs, counterexample) | `test_proofs.py::test_domain_derivatives_by_finite_differences`: the derivative formulas against finite differences of the closed formula of R, including a case with A < π and the counterexample M = 2 |

**Sample tests through the package** (consistency, not independence).

| Statement | Test |
|---|---|
| Propositions 4.1–4.5 | `test_real_eta.py::test_remainders_e6_and_monotonicities`, `::test_lambda_window_certifies_boundaries_and_empty_case`, `::test_lambda_window_near_two` (they call the package's `remainders`, `informative` and `lambda_window`) |
| Proposition 4.7 | `test_real_eta.py::test_trivial_regime_above_the_aliasing_threshold`: the threshold in closed form against `aliasing_exceeds_one` on both sides (η = 2.1, 2.5, 2.747, 2.748, 3, 3.5), and the enclosures just below and above it |
| Propositions 1.2, 1.6, 1.7 | `test_link_parameters.py::test_signal_lookup_extends_with_zero_and_one`, `::test_zero_gain_is_exactly_no_interference`, `::test_inr_scaling_overlaps_with_nondyadic_ratio`, `::test_tx_gain_folding_overlaps`, `::test_tx_link_scaling_alone_is_not_an_identity` |
| Proposition 1.3 | `test_link_parameters.py::test_from_link_two_thresholds_and_exact_context`, `::test_infeasible_allocation_precedes_division` |
| § 5 (first two cumulants) | `test_proofs.py::test_statement_c_and_cumulants`, against the extracted `moment` |

**No test of their own:** Propositions 1.1, 1.4 and Corollary 1.5, Lemma B0,
the certificate at the nodes (beyond its parts above) and Proposition 4.6.
End to end, the generated PPP envelopes are checked against L_J at three
points (G20); this consistency check does not replace the analytic bounds.
