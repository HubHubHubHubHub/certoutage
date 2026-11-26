"""Same sum of rectangles: group repeated CDF indices, in Arb."""
from .commun import *
class Grouped:
 def __init__(self,calc):
  self.calc=calc;self.prefix={}
  for J,(_,_,masses) in calc.levels.items():
   pair=[]
   for mass in masses:
    prefix=[arb(0)]
    for x in mass:prefix.append(prefix[-1]+x)
    pair.append(prefix)
   self.prefix[J]=pair
 def dot(self,index,values,prefix):
  cuts=np.r_[0,np.flatnonzero(index[1:]!=index[:-1])+1,len(index)]
  weights=[prefix[int(b)]-prefix[int(a)] for a,b in zip(cuts[:-1],cuts[1:])]
  vals=[values[int(index[int(a)])] for a in cuts[:-1]]
  return (arb_mat([weights])*arb_mat(len(vals),1,vals))[0,0]
 def point(self,db,methods=None,goal=.008):
  calc=self.calc;aa=calc.amplitude(db,1)
  for J in range(9,14):
   il,ih=calc.indices(aa,J);outcome={}
   for method,(lv,hv) in calc.arb_values.items():
    if methods is not None and method not in methods:continue
    lo=self.dot(il,lv,self.prefix[J][0]);hi=self.dot(ih,hv,self.prefix[J][1])+arb(float(calc.common['outside']))
    outcome[method]=(max(0.,out(lo)[0]),min(1.,out(hi)[1]))
   if all(arb(float(b))-arb(float(a))<=arb(str(goal))*arb(float(a)) for a,b in outcome.values()):break
  return outcome,J
