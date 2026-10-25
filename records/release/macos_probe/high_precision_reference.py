import json, mpmath as mp
mp.mp.dps=60
m=json.load(open("probe_macos_arm64.json")); l=json.load(open("probe_linux_karyon.json"))
g=lambda k: [mp.mpf(float.fromhex(x)) for x in m["inputs_hex"][k]]
rows=lambda v: [v[i:i+3] for i in range(0,len(v),3)]
P,Q,X,Y=[rows(g(k)) for k in "PQXY"]
n=len(P); Pc=[sum(r[j] for r in P)/n for j in range(3)]; Qc=[sum(r[j] for r in Q)/n for j in range(3)]
H=mp.matrix(3,3)
for i in range(3):
    for j in range(3):
        H[i,j]=sum((P[k][i]-Pc[i])*(Q[k][j]-Qc[j]) for k in range(n))
U,S,V=mp.svd_r(H)
d=mp.sign(mp.det(V.T*U.T)); Rm=V.T*mp.diag([1,1,d])*U.T
acc=mp.mpf(0)
for k in range(len(X)):
    y=Rm*mp.matrix([X[k][j]-Pc[j] for j in range(3)])
    acc+=sum((y[j]+Qc[j]-Y[k][j])**2 for j in range(3))
r=mp.sqrt(acc/len(X))
print("reference", mp.nstr(r,25), "float:", repr(float(r)))
for lab,v in (("macOS",m["report_value"]),("Linux",l["report_value"])):
    e=mp.mpf(v)-r; print(lab, repr(v), "error %s = %s ulp"%(mp.nstr(e,4), mp.nstr(e/mp.mpf(2)**-53,4)))
