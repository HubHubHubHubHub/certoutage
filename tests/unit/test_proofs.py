"""Numerical checks of the statements of docs/PROOFS.md (§ 3, § 4 and § 5).

The reference values of these checks do not come from the code that the
statements justify: Acb quadrature of the defining integrals, a distribution
with explicit CDF, direct sums, finite differences of the closed formula and
series with explicit remainders. A finite set of checked cases does not
replace the proofs.
"""
from fractions import Fraction

from flint import acb, arb
import pytest

from certoutage import _runtime as rt, _transform as tf
from certoutage._vendor.commun import moment


def _substitution(eta: str) -> tuple[int, int, int]:
    """r = v^(-p): returns p and the two integer exponents p*eta-2p-1, p*eta."""
    e = Fraction(eta)
    p = Fraction(2) if (2 * e).denominator == 1 and e >= Fraction(5, 2) else 1 / (e - 2)
    low, high = p * e - 2 * p - 1, p * e
    assert p.denominator == 1 and low.denominator == 1 and high.denominator == 1 and low >= 0
    return int(p), int(low), int(high)


def _narrow(value):
    """The quadrature reference must be a narrow ball, not merely finite."""
    value = acb(value)
    assert value.is_finite() and value.rad() < arb(2)**-40 * abs(value).lower()
    return value


def _J_by_quadrature(s: acb, eta: str) -> acb:
    """J(s) = ∫_1^∞ s r/(r^eta + s) dr = p s ∫_0^1 v^low/(1 + s v^high) dv."""
    p, low, high = _substitution(eta)
    return _narrow(acb.integral(lambda v, analytic: p * s * v ** low / (1 + s * v ** high),
                                0, 1, rel_tol=arb(2)**-60))


def _a_bound(tt, e):
    alpha = 2 / e
    return arb.pi() * abs(tt) ** alpha / (2 * e * (arb.pi() * alpha / 2).sin()) - arb(1) / 2


@pytest.mark.parametrize("c", ["1/1000", "20/128", "3"])
@pytest.mark.parametrize("eta", ["2.1", "2.25", "2.5", "3.5", "4", "8"])
def test_statement_a_majorant(eta, c):
    # |L_J(c+it)| <= exp(pi lam - beta |t|^alpha) for every lam > 0 is
    # equivalent to Re J(c+it) >= pi |t|^alpha / (2 eta sin(pi alpha/2)) - 1/2.
    # c=20/128 is the damping of the package; Statement A holds for every c > 0.
    with rt.arithmetic(160):
        e = arb(eta)
        cc = arb(Fraction(c).numerator) / Fraction(c).denominator
        for t in ("0", "0.5", "-3", "40", "-1000", "10000"):
            tt = arb(t)
            re = _J_by_quadrature(acb(cc, tt), eta).real
            bound = _a_bound(tt, e)
            assert re >= bound, (eta, c, t, re, bound)
        # The bound is not vacuous: the gap Re J - bound is positive, decreases
        # from |t| = 10^3 to 10^4 (it tends to 0, like |t|^(alpha-1)), and is
        # small compared with the bound itself.
        gaps, bounds = [], []
        for t in ("1000", "10000"):
            tt = arb(t)
            gaps.append(_J_by_quadrature(acb(cc, tt), eta).real - _a_bound(tt, e))
            bounds.append(_a_bound(tt, e))
        assert gaps[1] < gaps[0] and gaps[1] < bounds[1] / 100


def _levy_coefficients(B, c, K):
    """v_k = L_Y(z_k)/z_k for the Levy distribution L_Y(s) = exp(-sqrt(s))."""
    out = []
    for k in range(K + 1):
        s = acb(c, 2 * arb.pi() * k / B)
        out.append((-s.sqrt()).exp() / s)
    return out


def _truncation(coefficients, B, c, K, x):
    """T_K(x) by the direct sum of Statement B (half weight at rank K)."""
    total = coefficients[0].real
    for k in range(1, K):
        total += 2 * (coefficients[k] * acb(0, 2 * arb.pi() * k * x / B).exp()).real
    total += (coefficients[K] * acb(0, 2 * arb.pi() * K * x / B).exp()).real
    return (c * x).exp() / B * total


def test_statement_b_on_a_known_distribution():
    # Levy distribution of scale 1/2: L_Y(s) = exp(-sqrt(s)),
    # F_Y(x) = erfc(1/(2 sqrt(x))). On Re s > 0, |arg s| < pi/2 and
    # |s| >= |t|, so |L_Y(c+it)| <= exp(-|t|^(1/2)/sqrt(2)): A=1, b=1/sqrt 2, alpha=1/2.
    with rt.arithmetic(160):
        B, K = arb(8), 2048
        M = 2 * K
        c = arb(20) / B
        b, alpha = 1 / arb(2).sqrt(), arb(1) / 2
        xi = b * (2 * arb.pi() * K / B) ** alpha
        R = (-xi).exp() / arb.pi() * (arb(1) / (2 * K) + 1 / (alpha * xi))
        coefficients = _levy_coefficients(B, c, K)

        def F(x):
            return (1 / (2 * x.sqrt())).erfc()

        checked, ratios = 0, []
        for j in list(range(1, M, 257)) + [2, 3]:
            x = B * j / M
            T = _truncation(coefficients, B, c, K, x)
            # S(x) = sum_{l>=0} e^(-c l B) F(x + l B); omitted terms l >= 4 are
            # in [0, e^(-80)/(1-e^(-20))].
            S = sum((-(c * B * l)).exp() * F(x + B * l) for l in range(4))
            S += arb(0).union((-arb(80)).exp() / (1 - (-arb(20)).exp()))
            error, allowed = abs(S - T), (c * x).exp() * R
            assert allowed < arb("1e-5")  # the bound is informative at these nodes
            assert error <= allowed, (j, error, allowed)
            ratios.append(float((error / allowed).upper()))
            checked += 1
        assert checked == 18
        # The bound is nearly attained at the first nodes (observed ratio 0.49
        # at j=1 on 27/11/2026; much smaller at the other nodes): an R too small
        # by a factor 2.1 would fail. The bound also holds here with weight 0
        # or 1 at rank K (measured): this test checks the E_1 part of R and the
        # bound as a whole, not the half-weight convention, which is checked by
        # test_dft_identification_at_the_nodes.
        assert max(ratios) > 0.45


@pytest.mark.parametrize("K", [4, 8])
def test_dft_identification_at_the_nodes(K):
    # At x_j = jB/M, T_K(x_j) = (M/B) e^(c x_j) IFFT(V)_j with V_0 = v_0,
    # V_k = v_k, V_(M-k) = conj(v_k) for 0 < k < K, and V_K = Re(v_K).
    with rt.arithmetic(160):
        B, M = arb(8), 2 * K
        c = arb(20) / B
        v = _levy_coefficients(B, c, K)
        V = [None] * M
        V[0], V[K] = acb(v[0].real), acb(v[K].real)
        for k in range(1, K):
            V[k], V[M - k] = v[k], v[k].conjugate()
        ift = acb.dft(V, inverse=True)
        for j in range(M):
            x = B * j / M
            direct = _truncation(v, B, c, K, x)
            assert direct.overlaps((M / B * (c * x).exp() * ift[j]).real)
            # A full weight at rank K would differ at the nodes by
            # (e^(c x_j)/B) Re(v_K)(-1)^j, which is far from zero here.
            assert not direct.overlaps(direct + (c * x).exp() / B * v[K].real * (-1) ** j)


def _log_R(lam, eta, M, B=128):
    """log R of PROOFS § 4, recomputed from its closed formula (not by the package)."""
    alpha = 2 / eta
    omega = arb.pi() * M / B
    A = arb.pi() ** 2 * alpha * omega ** alpha / (2 * (arb.pi() * alpha / 2).sin())
    return (arb.pi() - A) * lam - arb.pi().log() + (arb(1) / M + 1 / (alpha * A * lam)).log(), A


@pytest.mark.parametrize("lam,eta,M", [("0.1", "4", 1 << 18), ("2", "2.1", 1 << 12),
                                       ("0.5", "8", 64), ("0.3", "4", 2)])
def test_domain_derivatives_by_finite_differences(lam, eta, M):
    lam_text, eta_text = lam, eta
    with rt.arithmetic(300):
        lam, eta = arb(lam), arb(eta)
        alpha = 2 / eta
        h = arb(2) ** -60
        log_R, A = _log_R(lam, eta, M)
        xi = lam * A
        d_lam = arb.pi() - A - 1 / (lam * (1 + alpha * A * lam / M))
        L = (arb.pi() * M / 128).log() + 1 / alpha - arb.pi() / 2 / (arb.pi() * alpha / 2).tan()
        d_eta = 2 / eta ** 2 * (xi * L + (1 / alpha + L) / (1 + alpha * xi / M))
        fd_lam = (_log_R(lam + h, eta, M)[0] - _log_R(lam - h, eta, M)[0]) / (2 * h)
        fd_eta = (_log_R(lam, eta + h, M)[0] - _log_R(lam, eta - h, M)[0]) / (2 * h)
        assert abs(fd_lam - d_lam) < arb(2) ** -50 * (1 + abs(d_lam))
        assert abs(fd_eta - d_eta) < arb(2) ** -50 * (1 + abs(d_eta))
        if M >= 64:  # Omega >= 1: Proposition 4.3, and A > pi (Proposition 4.1)
            assert L > 0 and A > arb.pi() and d_eta > 0 and d_lam < 0
        else:        # the counterexample of Proposition 4.3, with A < pi
            assert L < -2 and d_eta < 0 and A < arb.pi()
    if M >= 1 << 12:  # the package's R is the same closed formula
        with rt.arithmetic(160):
            assert tf.remainders(lam_text, eta_text, M.bit_length() - 1)[0].overlaps(log_R.exp())


@pytest.mark.parametrize("eta", ["2.1", "2.5", "3.5", "8"])
def test_statement_c_and_cumulants(eta):
    with rt.arithmetic(160):
        e = arb(eta)
        p, _, high = _substitution(eta)
        low = high - 2 * p - 1
        # log E e^(J/2) / (2 pi lam) = ∫_1^∞ r/(2 r^eta - 1) dr, by quadrature.
        integral = _narrow(acb.integral(lambda v, analytic: p * v ** low / (2 - v ** high),
                                        0, 1, rel_tol=arb(2)**-60)).real
        # The integral inequality of Statement C: at most ∫_1^∞ r^(1-eta) dr = 1/(eta-2).
        # (The exponential formula and Markov's step are not checked numerically.)
        assert integral <= 1 / (e - 2)
        # § 5: the same quantity is sum_j (1/2)^j/(j eta - 2); the terms are
        # decreasing, the tail after N terms is at most 2 (1/2)^(N+1)/((N+1)eta-2).
        N = 200
        series = sum(arb(1) / 2 ** j / (j * e - 2) for j in range(1, N + 1))
        series += arb(0).union(2 / arb(2) ** (N + 1) / ((N + 1) * e - 2))
        assert integral.overlaps(series)
        # Consistency, not independence: the cumulants returned by the extracted
        # `moment`, which the package uses for tau and the Gamma comparator.
        for lam in ("0.1", "2.5"):
            assert moment(lam, e, 1, 1).overlaps(2 * arb.pi() * arb(lam) / (e - 2))
            assert moment(lam, e, 1, 2).overlaps(2 * arb.pi() * arb(lam) / (e - 1))
