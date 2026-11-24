# Corrected public runtime: verifies the excluded left endpoint.
"""Numerical routines for certified Poisson-interference calculations."""
from .commun import *
from .ppp import envelopes

def down(x):
    return np.maximum(0.0, np.nextafter(x, -np.inf))

def up(x):
    return np.nextafter(x, np.inf)

class Signal:

    def __init__(self, N):
        self.N = N
        with np.load(ROOT / f'banques/SIG_{N}.npz') as z:
            self.values = {m: ([arb(float(x)) for x in np.maximum.accumulate(z[m][0, ::-1])], [arb(float(x)) for x in np.minimum.accumulate(z[m][1])[::-1]]) for m in ['exact', 'gauss']}
        self.size = len(self.values['exact'][0])
        thresholds = [out((-arb(j) * arb(10).log() / 1280).exp()) for j in range(96 * 128, -64 * 128 - 1, -1)]
        self.tlo = np.array([a for a, b in thresholds])
        self.thi = np.array([b for a, b in thresholds])
        assert len(self.tlo) == self.size

    def indices(self, yl, yh):
        il = np.searchsorted(self.thi, yl, side='right') - 1
        ih = np.searchsorted(self.tlo, yh, side='left')
        return (il, ih)

    def lookup(self, il, ih, method):
        lv, hv = self.values[method]
        n = self.size
        low = [arb(0) if i < 0 else lv[min(int(i), n - 1)] for i in il]
        high = [arb(1) if i >= n else hv[max(0, int(i))] for i in ih]
        return (low, high)

class Environment:

    def __init__(self, lam, eta, kind):
        self.lam = lam
        self.eta = eta
        self.kind = kind
        if kind == 'mean':
            mean = moment(lam, eta, 1, 1)
            a, b = out(mean)
            self.xlo = np.array([a])
            self.xhi = np.array([b])
            wl = wh = [arb(1)]
            self.tail = arb(0)
        else:
            name = 'l' + str(float(lam)).replace('.', 'p') + '_e' + str(eta)
            with np.load(ROOT / f'banques/{kind}_{name}.npz') as z:
                self.xlo = z['xlo']
                self.xhi = z['xhi']
                wl, wh, self.tail = envelopes(z['clo'], z['chi'], self.xlo, self.xhi)
        self.wl = arb_mat([wl])
        self.wh = arb_mat([wh])
        self.length = len(wl)

    def point(self, signal, units, convention, user, method='exact'):
        if units is None:
            if convention == 'C-INR':
                return dict(lower=0.0, upper=0.0)
            nlo = nhi = 0.0
        else:
            nlo, nhi = out((-arb(units) * arb(10).log() / 1280).exp())
        if convention == 'C-INR':
            yl = down(down(self.xlo + 1) * nlo)
            yh = up(up(self.xhi + 1) * nhi)
        else:
            yl = down(self.xlo + nlo)
            yh = up(self.xhi + nhi)
        if user == 2:
            yl = down(yl * 6)
            yh = up(yh * 6)
        il, ih = signal.indices(yl, yh)
        low, high = signal.lookup(il, ih, method)
        lo = (self.wl * arb_mat(self.length, 1, low))[0, 0]
        hi = (self.wh * arb_mat(self.length, 1, high))[0, 0] + self.tail
        return dict(lower=max(0.0, out(lo)[0]), upper=min(1.0, out(hi)[1]))

def dimension(fn, floor, target):
    p = arb(str(target))
    left = -40 * 16
    right = 96 * 16
    if arb(floor['lower']) > p:
        return dict(status='INATTEIGNABLE', lower_db=None, upper_db=None, undecided=None, floor=floor)

    def first(condition):
        if condition(fn(left * 8)):
            return left
        if not condition(fn(right * 8)):
            return None
        a, b = (left, right)
        while b - a > 1:
            mid = (a + b) // 2
            if condition(fn(mid * 8)):
                b = mid
            else:
                a = mid
        return b
    good = first(lambda r: arb(r['upper']) <= p)
    not_bad = first(lambda r: arb(r['lower']) <= p)
    bad = not_bad - 1 if not_bad is not None else right
    # The interval may be censored at the search boundary. Never invent an
    # excluded point to the left of the domain, even if the first point is good.
    if bad < left or not arb(fn(bad * 8)['lower']) > p:
        return dict(status='CENSURE_GAUCHE' if good is not None else 'BORNE_GAUCHE_INDECISE',
                    lower_db=None, upper_db=good / 16 if good is not None else None,
                    undecided=None, floor=floor)
    return dict(status='FINI' if good is not None else 'PLANCHER_INDECIDE' if arb(floor['upper']) >= p else 'HORS_GRILLE', lower_db=bad / 16, upper_db=good / 16 if good is not None else None, undecided=good - bad - 1 if good is not None else None, floor=floor)

def difference(a, b):
    if a['status'] == 'FINI' and b['status'] == 'FINI':
        return dict(status='FINI', lower=a['lower_db'] - b['upper_db'], upper=a['upper_db'] - b['lower_db'])
    if a['status'] == 'FINI' and b['status'] == 'INATTEIGNABLE':
        return dict(status='MOINS_INFINI', lower=None, upper=None)
    if a['status'] == 'INATTEIGNABLE' and b['status'] == 'FINI':
        return dict(status='PLUS_INFINI', lower=None, upper=None)
    return dict(status='NON_DEFINI', lower=None, upper=None)

def calibration(fn, target):
    a, b = (-40 * 128, 96 * 128)
    middle = lambda r: (r['lower'] + r['upper']) / 2
    assert middle(fn(a)) > target and middle(fn(b)) < target
    while b - a > 1:
        m = (a + b) // 2
        if middle(fn(m)) > target:
            a = m
        else:
            b = m
    va, vb = (fn(a), fn(b))
    return (a, va) if abs(middle(va) - target) <= abs(middle(vb) - target) else (b, vb)
