import csv, numpy as np, torch
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import batch_to_device
D="onet/db_31_0_csv/"
model=SentenceTransformer("TechWolf/JobBERT-v2")
def enc(texts,bs=64):
    out=[]
    for i in range(0,len(texts),bs):
        f=model.tokenize(texts[i:i+bs]); f=batch_to_device(f,model.device); f["text_keys"]=["anchor"]
        with torch.no_grad(): out.append(model.forward(f)["sentence_embedding"].cpu().numpy())
    e=np.vstack(out); return e/np.linalg.norm(e,axis=1,keepdims=True)
occ_title={r["O*NET-SOC Code"]:r["Title"] for r in csv.DictReader(open(D+"occupation_data.csv",encoding="utf-8"))}
pairs=[(t,c) for c,t in occ_title.items()]
pairs+=[(r["Reported Job Title"],r["O*NET-SOC Code"]) for r in csv.DictReader(open(D+"sample_of_reported_titles.csv",encoding="utf-8"))]
um=sorted({r["career_title"] for r in csv.DictReader(open("um_career_prospects.csv",encoding="utf-8"))})
E_on=enc([p[0] for p in pairs]); E_um=enc(um)
codes=sorted(occ_title); idx={c:i for i,c in enumerate(codes)}
S_=E_um@E_on.T
best=np.full((len(um),len(codes)),-1.0); via=[[None]*len(codes) for _ in um]
for j,(t,c) in enumerate(pairs):
    col=S_[:,j]; k=idx[c]; upd=col>best[:,k]
    best[upd,k]=col[upd]
    for i in np.where(upd)[0]: via[i][k]=t
with open("jobbert_top3.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["um_title","rank","onet_code","onet_title","similarity","matched_via"])
    for i,t in enumerate(um):
        for r,k in enumerate(np.argsort(-best[i])[:3]):
            w.writerow([t,r+1,codes[k],occ_title[codes[k]],round(float(best[i,k]),4),via[i][k]])
top=best.max(1); print("top-1 similarity quantiles:",np.round(np.quantile(top,[.1,.25,.5,.75,.9]),3))
