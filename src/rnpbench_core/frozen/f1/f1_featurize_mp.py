#!/usr/bin/env python
"""RNP-F1' featurizer: build (input Boltz, native target) frame tensors per complex.

For each complex: take the top-ipTM Boltz pose (input) and the native (target),
select the contacting protein+RNA chain pair in each, align sequences, and emit:
  - protein: per-residue backbone frame (N,CA,C -> rotation R, translation t=CA),
    residue type index, interface flag (native heavy-atom contact <5A)
  - RNA: per-nucleotide C4' coord, base-atom for orientation, nt type, interface flag
  - input (Boltz) and target (native) coordinates in a COMMON frame:
    superpose Boltz onto native on matched protein CA (Kabsch), apply to whole Boltz pose.
The refiner learns input-frames -> target-frames. Interface = the F0-established
bottleneck region, up-weighted in loss.

Caches one .pt per complex in outputs/rnp/f1/cache/. Read-only wrt structures.
"""
import os, sys, glob, csv, warnings, pickle
warnings.filterwarnings("ignore")
import numpy as np
from Bio.PDB import MMCIFParser, PDBParser, NeighborSearch

ROOT="/home/jwen/projects/PCfold3D-RNP"
FR=ROOT+"/outputs/rnp/fullrun"
CACHE=FR+"/../f1/cache"; os.makedirs(CACHE,exist_ok=True)
CACHE_MP=FR+"/../f1/cache_mp"; os.makedirs(CACHE_MP,exist_ok=True)
RNA_RES={"A","U","G","C","RA","RU","RG","RC"}
AA3={'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E','GLY':'G',
     'HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F','PRO':'P','SER':'S',
     'THR':'T','TRP':'W','TYR':'Y','VAL':'V'}
AA_IDX={a:i for i,a in enumerate("ARNDCQEGHILKMFPSTWYVX")}
NT_IDX={'A':0,'U':1,'G':2,'C':3,'N':4}
def nt1(rn):
    rn=rn.strip()
    if rn in ('A','RA'):return 'A'
    if rn in ('U','RU'):return 'U'
    if rn in ('G','RG'):return 'G'
    if rn in ('C','RC'):return 'C'
    return 'N'
def is_rna(r): return r.resname.strip() in RNA_RES
def is_aa(r): return r.id[0]==" " and r.resname.strip() in AA3 and ('CA' in r)

def load(path):
    p=(MMCIFParser if path.endswith('.cif') else PDBParser)(QUIET=True)
    return p.get_structure("s",path)

def chain_kind(ch):
    rna=sum(1 for r in ch if is_rna(r)); aa=sum(1 for r in ch if is_aa(r))
    if rna>=3 and rna>=aa: return "rna",rna
    if aa>=5: return "prot",aa
    return None,0

def contacting_pair(struct,cutoff=6.0):
    model=next(iter(struct)); prot={};rna={}
    for ch in model:
        k,_=chain_kind(ch)
        if k=="prot":prot[ch.id]=ch
        elif k=="rna":rna[ch.id]=ch
    if not prot or not rna: return None,None
    best=None;bn=-1
    for pid,pch in prot.items():
        pa=[a for r in pch if is_aa(r) for a in r]
        if not pa: continue
        ns=NeighborSearch(pa)
        for rid,rch in rna.items():
            ra=[a for r in rch if is_rna(r) for a in r]
            c=sum(1 for a in ra[::3] if ns.search(a.coord,cutoff))
            if c>bn: bn=c;best=(pid,rid)
    if best is None or bn==0:
        pid=max(prot,key=lambda k:chain_kind(prot[k])[1])
        rid=max(rna,key=lambda k:chain_kind(rna[k])[1])
        return pid,rid
    return best

def prot_frames(chain):
    """return list of (resid, aa1, N,CA,C coords)"""
    out=[]
    for r in chain:
        if not is_aa(r): continue
        try: N,CA,C=r['N'].coord,r['CA'].coord,r['C'].coord
        except KeyError: continue
        out.append((r.id[1],AA3[r.resname.strip()],N,CA,C))
    return out

def rna_atoms(chain):
    """return list of (resid, nt1, C4' coord, N-glyc coord or C1')"""
    out=[]
    for r in chain:
        if not is_rna(r): continue
        if "C4'" not in r: continue
        c4=r["C4'"].coord
        # glyc/base ref atom for orientation
        ref=None
        for an in ("N1","N9","C1'"):
            if an in r: ref=r[an].coord;break
        out.append((r.id[1],nt1(r.resname),c4,ref if ref is not None else c4))
    return out

def kabsch(P,Q):
    """rotation+translation mapping P onto Q (both Nx3). returns R,t so that P@R.T+t ~ Q"""
    Pc=P-P.mean(0); Qc=Q-Q.mean(0)
    H=Pc.T@Qc; U,S,Vt=np.linalg.svd(H)
    d=np.sign(np.linalg.det(Vt.T@U.T)); D=np.diag([1,1,d])
    R=Vt.T@D@U.T
    t=Q.mean(0)-R@P.mean(0)
    return R,t


def _align_pose(nat,pose,npid,nrid,np_pf,np_rf,nat_pa_ns,nat_ra_ns):
    """align one pose to native, return (rna_in_c4, rna_in_ref, prot_in_frame arrays over matched idx) or None"""
    import difflib
    ppid,prid=contacting_pair(pose)
    if ppid is None: return None
    pp_pf=prot_frames(pose[0][ppid]); pp_rf=rna_atoms(pose[0][prid])
    if len(pp_pf)<5 or len(pp_rf)<2: return None
    ns="".join(x[1] for x in np_pf); ps="".join(x[1] for x in pp_pf)
    sm=difflib.SequenceMatcher(None,ns,ps,autojunk=False)
    pmatch=[]
    for b in sm.get_matching_blocks():
        for k in range(b.size): pmatch.append((b.a+k,b.b+k))
    if len(pmatch)<5: return None
    natCA=np.array([np_pf[i][3] for i,_ in pmatch]); poseCA=np.array([pp_pf[j][3] for _,j in pmatch])
    R,t=kabsch(poseCA,natCA)
    def ap(x): return (R@np.asarray(x))+t
    nr="".join(x[1] for x in np_rf); pr="".join(x[1] for x in pp_rf)
    smr=difflib.SequenceMatcher(None,nr,pr,autojunk=False)
    rmatch=[]
    for b in smr.get_matching_blocks():
        for k in range(b.size): rmatch.append((b.a+k,b.b+k))
    if len(rmatch)<2: return None
    # matched protein frames (input) in native order used by build's pmatch — must match native pmatch!
    return dict(pmatch=pmatch,rmatch=rmatch,ap=ap,pp_pf=pp_pf,pp_rf=pp_rf)

def build_all(entry, split):
    """Featurize ALL Boltz poses for a complex against native. Emits one record with a
    per-pose list of input RNA/protein geometry, all aligned into the native frame.
    Native target + interface labels computed ONCE (identical across poses)."""
    natp=FR+f"/natives/{entry}.cif"
    poses=sorted(glob.glob(FR+f"/boltz_out/boltz_results_{entry}/predictions/{entry}/{entry}_model_*.pdb"))
    if not os.path.exists(natp) or not poses: return None,"no_files"
    nat=load(natp)
    npid,nrid=contacting_pair(nat)
    if npid is None: return None,"no_pair"
    np_pf=prot_frames(nat[0][npid]); np_rf=rna_atoms(nat[0][nrid])
    if len(np_pf)<5 or len(np_rf)<2: return None,"too_small"
    # native interface neighbor searches
    nat_pa=[a for r in nat[0][npid] if is_aa(r) for a in r]; ns_prot=NeighborSearch(nat_pa)
    nat_ra=[a for r in nat[0][nrid] if is_rna(r) for a in r]; ns_rna=NeighborSearch(nat_ra)
    poses_out=[]
    for pz in poses:
        try: pose=load(pz)
        except Exception: continue
        al=_align_pose(nat,pose,npid,nrid,np_pf,np_rf,ns_prot,ns_rna)
        if al is None: continue
        # build arrays consistently over the SAME native match indices as the target.
        # We anchor everything on the pose's own pmatch/rmatch (nat idx -> pose idx),
        # producing target (native) and input (pose) arrays over identical nat indices.
        pmatch=al["pmatch"]; rmatch=al["rmatch"]; ap=al["ap"]; pp_pf=al["pp_pf"]; pp_rf=al["pp_rf"]
        prot_type=[];prot_nat_frame=[];prot_in_frame=[];prot_iface=[]
        for ni,pj in pmatch:
            rid_,aa,N,CA,C=np_pf[ni]
            prot_type.append(AA_IDX.get(aa,20)); prot_nat_frame.append((N,CA,C))
            _,_,N2,CA2,C2=pp_pf[pj]; prot_in_frame.append((ap(N2),ap(CA2),ap(C2)))
            prot_iface.append(1 if ns_rna.search(CA,8.0) else 0)
        rna_type=[];rna_nat_c4=[];rna_nat_ref=[];rna_in_c4=[];rna_in_ref=[];rna_iface=[]
        nat_chain_ids=[r.id for r in nat[0][nrid]]
        for ni,pj in rmatch:
            rid_,nt,c4,ref=np_rf[ni]
            rna_type.append(NT_IDX.get(nt,4)); rna_nat_c4.append(c4); rna_nat_ref.append(ref)
            _,_,c4p,refp=pp_rf[pj]; rna_in_c4.append(ap(c4p)); rna_in_ref.append(ap(refp))
            key=(' ',rid_,' ')
            atoms_here=[a for a in nat[0][nrid][key]] if key in nat_chain_ids else []
            rna_iface.append(1 if (atoms_here and ns_prot.search(np_rf[ni][2],5.0)) else 0)
        poses_out.append(dict(
            pose=os.path.basename(pz),
            prot_type=np.array(prot_type,np.int64),
            prot_iface=np.array(prot_iface,np.int8),
            prot_in_frame=np.array(prot_in_frame,np.float32),
            prot_nat_frame=np.array(prot_nat_frame,np.float32),
            rna_type=np.array(rna_type,np.int64),
            rna_iface=np.array(rna_iface,np.int8),
            rna_in=np.stack([np.array(rna_in_c4,np.float32),np.array(rna_in_ref,np.float32)],1),
            rna_nat=np.stack([np.array(rna_nat_c4,np.float32),np.array(rna_nat_ref,np.float32)],1)))
    if not poses_out: return None,"no_aligned_pose"
    return dict(entry=entry,split=split,poses=poses_out),"ok"

def main():
    man={r["entry"]:r for r in csv.DictReader(open(FR+"/rnp_f1_dataset_manifest.tsv"),delimiter="\t")}
    only=sys.argv[1].split(",") if len(sys.argv)>1 and sys.argv[1]!="ALL" else sorted(man)
    stats={}
    for i,e in enumerate(only):
        outp=CACHE_MP+f"/{e}.pkl"
        if os.path.exists(outp): stats["cached"]=stats.get("cached",0)+1; continue
        try:
            d,why=build_all(e,man[e]["split"])
        except Exception as ex:
            why=f"err:{type(ex).__name__}"; d=None
        stats[why]=stats.get(why,0)+1
        if d is not None: pickle.dump(d,open(outp,"wb"))
        if (i+1)%50==0: print(f"{i+1}/{len(only)} {stats}",flush=True)
    print("DONE",stats)
if __name__=="__main__": main()
