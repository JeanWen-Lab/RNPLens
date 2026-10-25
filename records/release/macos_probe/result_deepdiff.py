"""Deep comparison of a fresh Report result.json (import + analyse of the bundled 7K9D example) with the rc3 expected
output. CK=<checkout> TMPDIR=<scratch> PYTHONPATH=<checkout>/src python result_deepdiff.py"""
import json, os, sys, struct, tempfile
sys.path.insert(0, os.path.join(os.environ["CK"], "tests"))
from rnplens import importer, analyse
CK=os.environ["CK"]; EX=os.path.join(CK,"examples"); RF=os.path.join(EX,"reference_free","report_7K9D")
PS=importer.read_sequence_arg(os.path.join(EX,"reference_based","7K9D_protein.fasta")); RS=importer.read_sequence_arg(os.path.join(EX,"reference_based","7K9D_rna.fasta"))
t=tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    assert importer.run([os.path.join(RF,"exec_A"),os.path.join(RF,"exec_B")],PS,RS,t+"/p","7K9D_example","BOLTZ2")==0
    assert analyse.run(t+"/p",t+"/r")==0
got=json.load(open(t+"/r/report/result.json")); exp=json.load(open(os.path.join(EX,"expected_output","B1_report_7K9D","result.json")))
diffs=[]; nnum=[0]
def u(x): return struct.unpack('<q',struct.pack('<d',x))[0]
def walk(a,b,p):
    if isinstance(a,dict) and isinstance(b,dict):
        for kk in sorted(set(a)|set(b)): walk(a.get(kk,"<absent>"),b.get(kk,"<absent>"),p+"/"+str(kk))
    elif isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        for i,(x,y) in enumerate(zip(a,b)): walk(x,y,p+"/%d"%i)
    elif isinstance(a,float) and isinstance(b,float):
        nnum[0]+=1
        if a!=b: diffs.append((p,repr(a),repr(b),abs(a-b),u(a)-u(b)))
    elif a!=b: diffs.append((p,str(a)[:80],str(b)[:80],None,None))
walk(got,exp,"")
print("floats compared", nnum[0]); print("differences", len(diffs))
for d in diffs: print(d)
