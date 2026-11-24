"""Inversion PPP extraite de ppp/code/champ.py, désormais fonction pure.

M est paramétrable ; toutes les bornes de reste utilisent le M effectivement
choisi. Les queues et les masses résiduelles ne sont jamais renormalisées.
"""
from __future__ import annotations

import math
import numpy as np
from flint import arb, acb, arb_mat

from ._vendor.commun import out, moment
from ._vendor.ppp import transform, envelopes
from ._vendor.thermal_backend import tighten, gamma_cdf


def _check_laplace(lam: str, eta: int, xlo, xhi, clo, chi) -> None:
    """Archive consistency guard; the omitted mass at +infinity contributes zero."""
    wl, wh, _ = envelopes(clo, chi, xlo, xhi)
    for s in ("0.1", "0.5", "1"):
        lv = [(-arb(s) * arb(float(x))).exp() for x in xlo]
        hv = [(-arb(s) * arb(float(x))).exp() for x in xhi]
        lap_hi = (arb_mat([wl]) * arb_mat(len(lv), 1, lv))[0, 0]
        lap_lo = (arb_mat([wh]) * arb_mat(len(hv), 1, hv))[0, 0]
        exact = transform(arb(s), lam, eta).real
        if not (lap_lo.lower() <= exact.upper() and lap_hi.upper() >= exact.lower()):
            raise ArithmeticError(f"Contrôle de Laplace incohérent : lam={lam}, eta={eta}, "
                                  f"s={s}, lower={lap_lo}, upper={lap_hi}, direct={exact}")


def environment_arrays(lam: str, eta: int, power: int, kind: str) -> dict:
    B = 128
    M = 1 << power
    K = M // 2
    c = arb(20) / B
    H = math.floor(float((10 * arb(129).log() / arb(10).log() * 256).mid()))
    xx = [(arb(j) * arb(10).log() / 2560).exp() - 1 for j in range(H + 1)] + [arb(B)]
    xx[0] = arb(0)
    xlo = np.array([max(0.0, out(x)[0]) for x in xx])
    xhi = np.array([max(0.0, out(x)[1]) for x in xx])
    xlo[0] = xhi[0] = 0
    if kind == "GAMMA":
        m1 = moment(lam, eta, 1, 1)
        m2 = moment(lam, eta, 1, 2)
        shape, scale = m1 * m1 / m2, m2 / m1
        gcdf = np.array([out(gamma_cdf(x / scale, shape)) if j else (0.0, 0.0)
                         for j, x in enumerate(xx)]).T
        clo, chi = tighten(*gcdf)
    else:
        alpha = arb(2) / eta
        beta = arb.pi() ** 2 * arb(lam) * alpha / (2 * (arb.pi() * alpha / 2).sin())
        zeta = beta * (2 * arb.pi() * K / B) ** alpha
        freq = (arb.pi() * arb(lam) - zeta).exp() / arb.pi() * (arb(1) / (2 * K) + 1 / (alpha * zeta))
        tail = (-arb(B) / 2 + moment(lam, eta, 1, 1)).exp()
        # If the absolute Fourier remainder already exceeds one, avoid a
        # costly inversion and possibly overflowing binary64 transport.
        # These are still valid CDF bounds; keep the analytic tail at B.
        if freq > 1:
            clo, chi = np.zeros(len(xx)), np.ones(len(xx))
            chi[0] = 0
            clo[-1] = max(0.0, out(1 - tail)[0])
            _check_laplace(lam, eta, xlo, xhi, clo, chi)
            return dict(xlo=xlo, xhi=xhi, clo=clo, chi=chi)
        alias = tail / arb(20).expm1()
        a0 = 1 / arb(20).expm1()
        coeff = [None] * M
        for k in range(K + 1):
            s = acb(c, 2 * arb.pi() * k / B)
            v = transform(s, lam, eta) / s
            if k == 0 or k == K:
                coeff[k] = acb(v.real)
            else:
                coeff[k] = v
                coeff[M - k] = v.conjugate()
        ft = acb.dft(coeff, inverse=True)
        del coeff
        lo, hi = np.empty(M + 1), np.empty(M + 1)
        for j in range(M):
            ex = (arb(20) * j / M).exp()
            v = ft[j].real * ex * M / B - a0
            lo[j], hi[j] = out(v + arb(0, (freq * ex).upper()) + arb(0).union(alias))
        del ft
        lo[0] = hi[0] = 0
        lo[M], hi[M] = out(1 - tail)[0], 1
        lo, hi = tighten(lo, hi)
        il = np.maximum(0, np.floor(np.nextafter(xlo * M / B, -np.inf))).astype(int)
        ih = np.minimum(M, np.ceil(np.nextafter(xhi * M / B, np.inf))).astype(int)
        clo, chi = lo[il], hi[ih]
        clo[0] = chi[0] = 0
        _check_laplace(lam, eta, xlo, xhi, clo, chi)
    return dict(xlo=xlo, xhi=xhi, clo=clo, chi=chi)
