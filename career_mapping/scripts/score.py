"""Scores the pre-registered mapping rules R1-R6 against the reviewer labels.
Run from career_mapping/data/mapping_eval/. Multi-letter answers ("A,C") = any listed option is acceptable."""
import csv, json, re, statistics as st
from openpyxl import load_workbook
P="PRIVATE_do_not_share/"
key={int(r["no"]):(r["um_title"],json.loads(r["options"])) for r in csv.DictReader(open(P+"review_PRIVATE_option_key.csv",encoding="utf-8"))}
def labels(n):
    ws=load_workbook(f"for_reviewers/review_Reviewer_{n}.xlsx")["Review"]; out={}
    for r in ws.iter_rows(min_row=2):
        no=r[0].value; a=str(r[11].value or "").upper().strip(); opts=key[no][1]
        if a=="NONE": out[no]={"NONE"}
        elif a.startswith("OTHER"): out[no]={str(r[12].value).strip()}
        else: out[no]={opts[l] for l in re.findall(r"[A-H]",a)}
    return out
A,B=labels("A"),labels("B")
multiA={no for no,s in A.items() if len(s)>1}
title={no:t for no,(t,_) in key.items()}
cur={r["um_title"]:r["onet_code"] for r in csv.DictReader(open(P+"method_curated.csv",encoding="utf-8"))}
jb={r["um_title"]:r["onet_code"] for r in csv.DictReader(open(P+"jobbert_top3.csv",encoding="utf-8")) if r["rank"]=="1"}
gmr={r["um_title"]:r for r in csv.DictReader(open(P+"method_gemini.csv",encoding="utf-8"))}
def rules(t):
    c=cur[t] if cur[t]!="NONE" else None; j=jb[t]; g=gmr[t]["onet_code"] if gmr[t]["onet_code"]!="NONE" else None
    agree=g if g and g==j else None
    return {"R1 Curated only":c,"R2 JobBERT only":j,"R3 Gemini only":g,"R4 Curated>Gemini":c or g,
            "R5 Curated>agree>Gemini":c or agree or g,"R6 Curated>agree>unmapped":c or agree}
agreeAB={no for no in A if A[no]&B[no]}
def score(ref,items):
    rows=[]
    for rule in rules(title[1]).keys():
        mapped=correct=0
        for no in items:
            out=rules(title[no])[rule]
            if out: mapped+=1; correct+= out in ref[no]
            elif "NONE" in ref[no]: correct+=1
        rows.append((rule,len(items),mapped,correct))
    return rows
def show(name,ref,items):
    print(f"\n### {name}  (n={len(items)})")
    print(f"{'Rule':28}{'Mapped':>8}{'Correct':>9}{'Precision':>11}{'Coverage':>10}{'Accuracy(all)':>15}")
    for rule,n,m,c in score(ref,items):
        prec=f"{c/m:.0%}" if m else "-"
        print(f"{rule:28}{m:>8}{c:>9}{prec:>11}{m/n:>10.0%}{c/n:>15.0%}")
allno=sorted(key)
print(f"Reviewer agreement A vs B: {len(agreeAB)}/100 = {len(agreeAB)}%   (A multi-answers: {len(multiA)})")
print(f"  excluding A's multi-answer titles: {len(agreeAB-multiA)}/{100-len(multiA)} = {len(agreeAB-multiA)/(100-len(multiA)):.0%}")
consensus={no:A[no]&B[no] for no in agreeAB}
show("PRIMARY: titles where both reviewers agree",consensus,sorted(agreeAB))
show("vs Reviewer A (all 100)",A,allno)
show("vs Reviewer B (all 100)",B,allno)
show("SENSITIVITY: consensus, excluding A's multi-answer titles",consensus,sorted(agreeAB-multiA))
print("\n### Gemini confidence vs correctness (consensus titles)")
bins=[(0,.85),(.85,.9),(.9,.95),(.95,1.01)]
for lo,hi in bins:
    items=[no for no in agreeAB if lo<=float(gmr[title[no]]["confidence"])<hi]
    if items: print(f"  conf [{lo:.2f},{min(hi,1):.2f}): n={len(items):3}  correct={sum(gmr[title[no]]['onet_code'] in consensus[no] for no in items)/len(items):.0%}")
