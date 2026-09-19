"""Final scoring. Reviewer B = independent (primary). Reviewer A = system developer
(blind to option sources, but had seen JobBERT output for 4 sampled titles).
Reviewer C = independent tie-break on the 28 A/B-disputed titles.
Majority key: A&B agree -> that answer; else C's answer if it matches A or B; else no consensus."""
import re, sys
sys.argv=[sys.argv[0]]
exec(open("../../scripts/score.py",encoding="utf-8").read().split("agreeAB=")[0])
wsC=load_workbook("for_reviewers/review_Reviewer_C_tiebreak.xlsx")["Review"]
C={r[0].value:{key[r[0].value][1][l] for l in re.findall(r"[A-H]",str(r[11].value or "").upper())} for r in wsC.iter_rows(min_row=2)}
agreeAB={no for no in A if A[no]&B[no]}
majority={}; side={"A":0,"B":0,"neither":0}
for no in A:
    if no in agreeAB: majority[no]=A[no]&B[no]
    else:
        c=C[no]
        if c&A[no]: majority[no]=c&A[no]; side["A"]+=1
        elif c&B[no]: majority[no]=c&B[no]; side["B"]+=1
        else: side["neither"]+=1
EXPOSED={"Registered Nurse","Nurse Educator","Forensic Medical Officer","Mediator In Islamic Disputes"}
exposed_no={no for no in A if title[no] in EXPOSED}
def table(name,ref,items):
    print(f"\n### {name}  (n={len(items)})")
    print(f"{'Rule':28}{'Mapped':>8}{'Correct':>9}{'Precision':>11}{'Coverage':>10}")
    for rule,n,m,c in score(ref,items):
        print(f"{rule:28}{m:>8}{c:>9}{(f'{c/m:.0%}' if m else '-'):>11}{m/n:>10.0%}")
def score(ref,items):
    out=[]
    for rule in rules(title[1]):
        m=c=0
        for no in items:
            o=rules(title[no])[rule]
            if o: m+=1; c+= o in ref[no]
            elif "NONE" in ref[no]: c+=1
        out.append((rule,len(items),m,c))
    return out
print("Reviewer agreement A(developer) vs B(independent):",f"{len(agreeAB)}/100")
print("Tie-break on 28 disputed titles -> C sided with A:",side["A"],"| with B:",side["B"],"| neither (no consensus):",side["neither"])
table("PRIMARY: independent Reviewer B",B,sorted(B))
table("MAJORITY KEY (2 of 3 reviewers)",majority,sorted(majority))
table("SENSITIVITY: majority key, excluding the 4 titles the developer saw outputs for",majority,sorted(set(majority)-exposed_no))
table("SENSITIVITY: majority key, excluding A's 9 multi-answer titles",majority,sorted(set(majority)-{no for no in A if len(A[no])>1}))
print("\n### Gemini confidence vs correctness (majority key)")
for lo,hi in [(0,.85),(.85,.9),(.9,.95),(.95,1.01)]:
    it=[no for no in majority if lo<=float(gmr[title[no]]["confidence"])<hi]
    if it: print(f"  conf [{lo:.2f},{min(hi,1):.2f}): n={len(it):3}  correct={sum(gmr[title[no]]['onet_code'] in majority[no] for no in it)/len(it):.0%}")
