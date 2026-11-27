# Certification contract

## Mathematical object

With V_k=sqrt(E_k F_k), A_N=Σ V_k and W=A_N²(10+Z)²/101, the two quantities
are P_INR(ρ)=E F_W(d_i(1+gJ)/ρ) and P_TX(ρ)=E F_W(d_i(gJ+1/ρ)).
Every independence assumption of the model of the Letter is needed. The
results for the two users are marginal; no joint probability and no optimal
allocation of a shared surface is certified.

For physical intensity λ′, guard radius R0 and path-gain coefficient κ,
`lam` is λ′R0². With ρ=P/N0 and interferer power P_I independent of P,
g_INR=P_I κ R0^(−η)/N0; with P_I=aP, g_TX=aκR0^(−η).
The physical triple (λ′, R0, κ) is not identifiable from these probabilities:
only λ′R0² and the corresponding interference gain enter the normalized model.
This normalization, the monotonicity in d and g, the exact case g=0 and the
scaling identities have provisional proofs in [PROOFS.md](PROOFS.md#1-link-coefficients-and-interference-gain), § 1.

The inversion of the gain transform, the remainders and the thermal
rectangles come from the archive. The useful-gain banks are provided at
160 bits. The rectangles cover [-12, 12], with -10 and 0 on cell boundaries;
the omitted mass is bounded above by 2φ(12)/12. The zero of the thermal
factor is neither removed nor treated as a positive point probability.

## Composition of distributions

For a CDF enclosed at the nodes x_j by L_j and U_j, two stochastically
ordered discrete distributions are built. The masses are the differences of
ONE cumulative envelope; they are not replaced by independent mass
intervals. The lower residual is placed at the last finite node, the upper
one at +∞. For every nondecreasing test function g:
E g(X-) ≤ E g(J) ≤ E g(X+).

The API inherits, unchanged, `Signal.indices` and `Signal.lookup` from
`ppp/code/oracles.py`, and overrides `Environment.point` to apply g and
d_i/(80/3) with the same outward-rounding rules. Node lookups are
conservative, binary64 additions and products are widened with `nextafter`,
and masses and dot products stay in Arb. No linear interpolation and no
renormalization of tails is used.

The thermal parameters remain fixed; d1, d2 and g are free, with the Letter's
defaults. [`Model.from_link`](API.md#model-and-calculation) computes the link
coefficients exactly. An infeasible allocation gives outage 1 at every SNR,
including its limit; g=0 removes interference and gives a zero floor for a
finite d. A new λ does not justify
changing the gain bank; it changes the PPP distribution, which is
recomputed with the remainders below.

## On-demand PPP inversion

The accepted exponents are 2.1 ≤ η ≤ 8 (since 0.3.0), with
0 ≤ λ ≤ 10. The provisional proofs referred to below hold for every η > 2,
and the transform is tested by quadratures independent of its code at both
ends of the η range (G56, G63). The **usefulness** of the result, however,
depends on λ and η jointly: the mean interference μ_J=2πλ/(η−2) must stay
well inside the fixed window B=128. Near η=2 the informative domain D_M
below closes from above at λ_τ ≈ 6.52(η−2), and at λ ≥ λ_triv ≈ 13.37(η−2)
the enclosure is trivial (PROOFS.md, Proposition 4.7):

| η | λ_R (M=2^18) | λ_τ | λ_triv |
|---|---|---|---|
| 2.1 | 0.0016 | 0.652 | 1.337 |
| 2.2 | 0.0024 | 1.304 | 2.674 |
| 2.5 | 0.0069 | 3.261 | 6.685 |
| 3 | 0.024 | 6.521 | 13.37 (> 10) |
| 3.534 to 8 | 0.063 to 1.27 | ≥ 10 | > 10 |

So, for η < 2.748, part of the accepted λ range gives [0, 1]-like
enclosures, which are valid but carry no information (third contract
note below; G65). An end-to-end Monte Carlo comparison kept outside the
repository (48 cases, 0 disagreement) covers η from 2.10 to 7.95; below
η=2.5 it reaches λ from 0.004 to 1.86λ_τ (μ_J up to 76), that is, the upper
side of D_M up to just below λ_triv.
For η=3 or 4, the explicit expressions of the archive are used unchanged
for L_J(s)=exp(-2πλ J(s)), J(s)=∫_1^∞ sr/(r^η+s) dr, with principal branches.
Other η use the nonregularized Arb identities, on Re(s)>0, with α=2/η:
J(s)=s/(η−2) ₂F₁(1,1−α;2−α;−s) for |s|≤1, and
J(s)=πs^α/[η sin(πα)] − ½ ₂F₁(1,α;1+α;−1/s) otherwise.
Both identities hold throughout this half-plane; the midpoint-based choice
is numerical only ([PROOFS.md](PROOFS.md#2-laplace-transform-of-j-for-real-η), § 2). The exact relation a+b−c=0 is declared with `abc=True`
(F. Johansson, “Computing hypergeometric functions rigorously”, ACM TOMS
45(3), article 30, 2019, doi:10.1145/3328732). Nonfinite or overly wide
2F1 values trigger one precision doubling, then a Pfaff series with a
certified geometric remainder; failure raises `ArithmeticError`.
Let α=2/η, β=π²λα/[2 sin(πα/2)], B=128, cB=20, K=M/2 and
ξ=β(2πK/B)^α. The Fourier remainder is

R=exp(πλ-ξ)/π × (1/(2K)+1/(αξ)).

With τ=exp(-B/2+2πλ/(η-2)) and a0=1/expm1(20), the certificate at the
nodes x_j=jB/M, 0<j<M, is
T_K-a0-exp(cx)R ≤ F_J(x) ≤ T_K-a0+exp(cx)R+τa0,
where T_K is the truncated Fourier sum computed by the size-M DFT (noted
S_M in the archive). The Fourier majorant |L_J(c+it)| ≤ exp(πλ−β|t|^α),
the remainder R, the tail bound P(J>B) ≤ τ and this certificate have
provisional proofs for every η > 2, λ > 0 and M=2K in [PROOFS.md](PROOFS.md#3-fourier-bound-remainder-r-and-tail-τ-for-every-η--2), § 3.
F_J(0)=0. In the DFT branch, the **stored** enclosure at B is
F_J(B)∈[L_{M−1},1], where L is the lower envelope tightened on the uniform
nodes jB/M: the conservative lower index at B is M−1.
The analytic bound max(0,1−τ) is applied at the uniform node M, but is not
carried over into `clo[-1]` after this index selection.
In the R>1 branch without DFT, the stored enclosure at B is indeed
[max(0,1−τ),1], with outward binary64 transport. These choices can give a
weaker stored bound at B when M increases.
The constants, the DFT and the remainders are computed in Arb/Acb. The
composition nodes are those of the archive, x_j=10^(j/2560)-1, then B;
their abscissas are enclosed.

For ε_R=10⁻⁷ and ε_τ=10⁻¹⁰, the informative domain is
D_M={λ_R(η,M) ≤ λ ≤ λ_τ(η)}, where R(λ_R,η,M)=ε_R exp(−20) and
λ_τ=(B/2+log ε_τ)(η−2)/(2π). In the monotone regime πM/B≥1 (M≥41 for
B=128; every accepted M), λ_R is bracketed by certified bisection. Internal helpers `remainders`,
`informative` and `lambda_window` expose these bounds; the latter returns
binary64 brackets and an explicit empty-window flag (before intersection
with the technical λ range). The criteria exp(20)R≤ε_R and τ≤ε_τ bound only
the **analytic** width at nodes, by 2ε_R+a0 ε_τ: they do not bound monotone
discretization, signal-bank widths or evaluation errors. The monotonicity
of R and τ behind these bounds has a provisional proof in [PROOFS.md](PROOFS.md#4-the-informative-domain-d_m), § 4.
General-exponent PPP contracts announce inside/outside D_M, only when a PPP
inversion contributes: results with λ=0 or g=0 (exact case without
interference), infeasible allocations and analytic floors carry no such
note. Outside D_M no new rejection or numerical behavior is introduced;
valid certificates may be wide. "Outside" says only that the two analytic
criteria are not proved; it does not mean that the final enclosure is wide
(at small λ in particular, it can be narrow). When moreover τa0 ≥ 1
(λ ≥ λ_triv), a third note says so: every interior node of the
interference CDF then carries an error of at least 1, and the enclosure
should be expected to be trivial. Below λ_triv the term τa0 still widens the
enclosure (about 0.65 at η=2.1, λ=1.33).

The change from M=2^20 to a configurable M preserves this proof: ξ, K and
the discretization exponential use the effective M. It does not necessarily
preserve the width of the certificates. If R>1, the calculation returns the
CDF bounds [0,1], with the analytic tail bound at the last node, without
starting a useless DFT. This is an explicit coarse certificate, not an
extrapolation towards a better-conditioned case.

After PPP generation, the discrete envelopes are checked against L_J(s) at
the three values s=0.1, 0.5 and 1, as in `champ.py` of the archive. An
inconsistency raises `ArithmeticError`, even under `python -O`. This
consistency check does not replace the analytic bounds.

The Gamma branch uses the regularized Gamma CDF in Arb and, when needed, a
positive series with a geometric remainder or an exponential bound. Its
first two cumulants are those of J ([PROOFS.md](PROOFS.md#5-cumulants-of-j-and-the-gamma-comparator), § 5). This rigorous integration does not bound the bias
of the PPP → Gamma substitution.

## Particular contracts

The distribution of the largest interferer is
P(J_max≥x)=1-exp(-Λ(x)), Λ(x)=(2πλ/η)x^(-2/η)Γ(2/η,x), R0=1.
Since J_max≤J and g≥0, E F_W(d_i g J_max) is a **floor lower bound**. The returned
interval encloses this lower bound; its upper edge is not an upper bound on
the PPP floor. The archived central values are labelled
`provided-certificate`. Their `precision_bits` stays 160, even when a higher
precision was requested: no new integration is performed in this branch.

The Chernoff comparator is C_N(a)=inf_{s≥0} exp(sa)L(s)^N. The banks
enclose the propagated comparator within the same integrations. The root of
the optimization was certified by signs; the removable singularity near
s=2 uses a series with an established remainder. The lower endpoints of the
comparator are not lower endpoints of the outage. The API guarantees that
they never produce `excluded` for the physical model.

The recurrence of the Nakagami transform in the archive uses the integer
index 2m-1 and an explicit variation bound. It is not a certified routine
for arbitrary real m. For m=2, 3 the banks and their bounds are reused;
generation and stability for other m are not claimed.

## What is a proof and what is not

Mathematical validity is conditional on the analytic proofs referenced in
the Letter and in `notes/decisions/` of the archive, on the provisional
proofs of [PROOFS.md](PROOFS.md) for the general interface (free d1, d2, g
and real η), on the validity of Arb/Acb, and on the required IEEE arithmetic
being respected. PROOFS.md, § 6, states which of its statements are checked
by a test whose reference values do not come from the package (§ 2, 3 and
5, and the closed formulas of § 4), which only by sample tests through the
package (§ 1), and which have no test of their own (G63); these checks do not
replace the proofs. The package
extracts and tests this contract; it is neither a formal proof of the
engine nor a new independent proof of all the bounds of the paper.

A SHA-256 digest checks the integrity of the data against a reference
digest; it proves neither their provenance nor their correctness. A raw
regression attests that the tested calculations are preserved. The
cross-check of the new case at 192 bits with a doubled DFT adds a further
check, with the same 160-bit useful-gain bank; it is not an independent
proof.
