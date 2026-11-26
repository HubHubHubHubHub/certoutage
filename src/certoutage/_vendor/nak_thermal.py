from .thermal_backend import *
class Thermal:
    def __init__(self,N,m=1,with_chernoff=False):
        self.N=N
        with np.load('banques/m%d_N%d.npz'%(m,N)) as f:self.bank={k:f[k] for k in f.files}
        self.B=int(self.bank['B']);self.dx=self.B/M;self.common=np.load('banques/commun.npz');self.levels={};self.weights={}
        self.arb_values={}
        if with_chernoff:
            with np.load('banques/C_N%d.npz'%N) as f:
                self.bank.update({k:f[k] for k in ['chernoff_lo','chernoff_hi']})
        for name in (['exact','gauss','chernoff'] if with_chernoff else ['exact','gauss']):
            self.arb_values[name]=([arb(float(x)) for x in self.bank[name+'_lo']],[arb(float(x)) for x in self.bank[name+'_hi']])
        for J in range(9,14):
            step=1<<(13-J);z=self.common['z'][::step];ph=self.common['phi'][:,::step]
            left=np.abs(10+z[:-1]);right=np.abs(10+z[1:]);tmin=np.minimum(left,right);tmax=np.maximum(left,right)
            # The exported extremes are exact dyadics; mass computations are done in Arb.
            ml=[(arb(float(x))/(1<<J)).lower() for x in np.minimum(ph[0,:-1],ph[0,1:])]
            mh=[(arb(float(x))/(1<<J)).upper() for x in np.maximum(ph[1,:-1],ph[1,1:])]
            self.levels[J]=(tmin,tmax,(ml,mh));self.weights[J]=(arb_mat([ml]),arb_mat([mh]))
    def amplitude(self,db,user):
        d=arb(str(db));ci=arb(10)/3 if user==1 else arb(5)/2;lam=arb(1)/(8 if user==1 else 64)
        return outward((101*ci/((d*arb(10).log()/10).exp()*lam)).sqrt())
    def indices(self,aa,J):
        tmin,tmax,_=self.levels[J]
        # IEEE arithmetic only selects conservative indices; all products/sums are in Arb.
        al=np.maximum(0,np.nextafter(aa[0]/tmax,-np.inf))
        with np.errstate(divide='ignore'):ah=np.nextafter(aa[1]/tmin,np.inf)
        il=np.minimum(M,np.floor(np.maximum(0,np.nextafter(al/self.dx,-np.inf)))).astype(np.int64)
        ih=np.minimum(M,np.ceil(np.maximum(0,np.nextafter(ah/self.dx,np.inf)))).astype(np.int64)
        return il,ih
    def point(self,db,user=1,methods=('exact',),goal=.008):
        aa=self.amplitude(db,user);out={}
        for J in range(9,14):
            il,ih=self.indices(aa,J);wl,wh=self.weights[J];length=len(il)
            for name in methods:
                lv,hv=self.arb_values[name]
                lo=(wl*arb_mat(length,1,[lv[int(i)] for i in il]))[0,0]
                hi=(wh*arb_mat(length,1,[hv[int(i)] for i in ih]))[0,0]+arb(float(self.common['outside']))
                out[name]=(max(0.,outward(lo)[0]),min(1.,outward(hi)[1]))
            a,b=out[methods[0]]
            if a>0 and (arb(float(b))-arb(float(a)))<=arb(str(goal))*arb(float(a)):break
        return out,J
