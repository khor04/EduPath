import csv, re, collections
D="onet/db_31_0_csv/"
def norm(t):
    t=t.lower().replace("&"," and "); t=re.sub(r"[^a-z0-9 ]"," ",t); w=t.split()
    if w and len(w[-1])>3 and w[-1].endswith("s") and not w[-1].endswith("ss"): w[-1]=w[-1][:-1]
    return " ".join(w)
L=collections.defaultdict(set)
for r in csv.DictReader(open(D+"occupation_data.csv",encoding="utf-8")): L[norm(r["Title"])].add(r["O*NET-SOC Code"])
for r in csv.DictReader(open(D+"sample_of_reported_titles.csv",encoding="utf-8")): L[norm(r["Reported Job Title"])].add(r["O*NET-SOC Code"])
def cands(t):
    b=re.sub(r"\(.*?\)","",t).strip(); yield t
    if b!=t: yield b
    if "/" in b: yield from b.split("/")
um=sorted({r["career_title"] for r in csv.DictReader(open("um_career_prospects.csv",encoding="utf-8"))})
with open("method_curated.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["um_title","onet_code","candidates","status"])
    for t in um:
        hit=next((L[norm(c)] for c in cands(t) if L.get(norm(c))),set())
        w.writerow([t, next(iter(hit)) if len(hit)==1 else "NONE", ";".join(sorted(hit)),
                    "mapped" if len(hit)==1 else ("ambiguous" if hit else "no_match")])
print(collections.Counter(r["status"] for r in csv.DictReader(open("method_curated.csv",encoding="utf-8"))))
