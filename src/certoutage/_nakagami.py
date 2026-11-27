"""Integer Nakagami transforms, preserving the historical Arb operations.

These kernels use the caller's arithmetic context and have no cached Arb
constants. Generation entries select and restore precision and thread count.
"""
from flint import acb, arb


def constant(m):
    return 4 * arb(m) ** (2 * m) / arb.fac_ui(m - 1) ** 2


def mu(m):
    return arb(m + .5).gamma() ** 2 / (m * arb.fac_ui(m - 1) ** 2)


def variation(m):
    return 2 * m * (2 * m - 1) * arb(m - .5).gamma() ** 2 / arb.fac_ui(m - 1) ** 2


def integrals(s, m, last):
    s = acb(s)
    b = 2 * m
    d = s * s - b * b
    w = d.sqrt()
    vals = [((s + w) / b).log() / w]
    if last:
        vals.append((s * vals[0] - 1) / d)
    for k in range(1, last):
        vals.append(((2 * k + 1) * s * vals[k] - k * k * vals[k - 1]) / d)
    return vals


def L(s, m=1):
    return constant(m) * integrals(s, m, 2 * m - 1)[-1]
