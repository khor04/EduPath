"""Builds the BLIND reviewer workbook + a private key mapping options -> methods."""
import csv, json, random, glob, re
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
SEED=20260918; LETTERS="ABCDEFGHIJ"
D="onet/db_31_0_csv/"
occ={r["O*NET-SOC Code"]:(r["Title"],r["Description"]) for r in csv.DictReader(open(D+"occupation_data.csv",encoding="utf-8"))}
sample=list(csv.DictReader(open("../data/mapping_eval_sample.csv",encoding="utf-8")))
cur={r["um_title"]:r for r in csv.DictReader(open("method_curated.csv",encoding="utf-8"))}
jb={}
for r in csv.DictReader(open("jobbert_top3.csv",encoding="utf-8")): jb.setdefault(r["um_title"],[]).append(r["onet_code"])
gm={r["um_title"]:r for r in csv.DictReader(open("method_gemini.csv",encoding="utf-8"))}
rng=random.Random(SEED); key=[]
wb=Workbook(); ws=wb.active; ws.title="Review"
ws.append(["No","UM career title","Offered in programme(s)"]+[f"Option {l}" for l in LETTERS[:8]]+["YOUR ANSWER","If OTHER: O*NET code","Notes (optional)"])
for c in ws[1]: c.font=Font(bold=True,color="FFFFFF"); c.fill=PatternFill("solid",fgColor="1F4E78"); c.alignment=Alignment(wrap_text=True,vertical="top")
for i,s in enumerate(sample,1):
    t=s["um_title"]; pool=[]
    pool+= [c for c in cur[t]["candidates"].split(";") if c]
    pool+= jb.get(t,[])
    if gm.get(t) and gm[t]["onet_code"] in occ: pool.append(gm[t]["onet_code"])
    pool=list(dict.fromkeys(pool)); rng.shuffle(pool); pool=pool[:8]
    opts=[f"{occ[c][0]}  [{c}]" for c in pool]
    ws.append([i,t,s["programmes"]]+opts+[""]*(8-len(opts))+["","",""])
    key.append({"no":i,"um_title":t,"options":json.dumps(dict(zip(LETTERS,pool)))})
dv=DataValidation(type="list",formula1='"A,B,C,D,E,F,G,H,OTHER,NONE"',allow_blank=True); ws.add_data_validation(dv); dv.add(f"L2:L{len(sample)+1}")
for col,wd in zip("ABCDEFGHIJKLMN",[5,34,34]+[30]*8+[13,16,28]): ws.column_dimensions[col].width=wd
for row in ws.iter_rows(min_row=2):
    for c in row: c.alignment=Alignment(wrap_text=True,vertical="top")
    row[11].fill=PatternFill("solid",fgColor="FFF2CC")
ws.freeze_panes="C2"
ref=wb.create_sheet("ONET occupations (search)")
ref.append(["O*NET code","Occupation title","Description"])
for c,(t,d) in occ.items(): ref.append([c,t,d])
for c in ref[1]: c.font=Font(bold=True)
ref.auto_filter.ref=f"A1:C{len(occ)+1}"; ref.column_dimensions["A"].width=12; ref.column_dimensions["B"].width=45; ref.column_dimensions["C"].width=120; ref.freeze_panes="A2"
ins=wb.create_sheet("Instructions",0)
for line in [
 "Career title mapping review",
 "",
 "Thank you for helping! For each Malaysian university career title on the 'Review' sheet, choose the ONE",
 "O*NET occupation whose MAIN DAILY WORK best represents that career.",
 "",
 "How to answer (column 'YOUR ANSWER', yellow):",
 "  • Pick a letter A–H if one of the listed options is the best fit. Options are in random order.",
 "  • Pick OTHER if a better occupation exists that is not listed. Find it on the 'ONET occupations (search)' sheet",
 "    (use the filter on the title/description columns) and write its code (e.g. 29-1141.00) in the next column.",
 "  • Pick NONE if no O*NET occupation reasonably represents the career. Do not force a weak match.",
 "",
 "Guidelines:",
 "  • Judge by main work duties, not by similar-sounding words.",
 "  • 'Offered in programme(s)' shows which UM degree lists this career — use it for context.",
 "  • Work alone — please don't discuss answers with other reviewers until you have finished.",
 "  • If unsure between two options, pick the better one and explain in Notes.",
]: ins.append([line])
ins["A1"].font=Font(bold=True,size=14); ins.column_dimensions["A"].width=120
for name in ["Reviewer_A","Reviewer_B"]: wb.save(f"review_{name}.xlsx")
with open("review_PRIVATE_option_key.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["no","um_title","options"]); w.writeheader(); w.writerows(key)
sizes=[len(json.loads(k["options"])) for k in key]
print("built; options per title min/avg/max:",min(sizes),round(sum(sizes)/len(sizes),1),max(sizes))
