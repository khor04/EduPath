import csv, json, os, re, time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
MODEL="gemini-3.6-flash"; BATCH=50; SPACING=15
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model=genai.GenerativeModel(MODEL, generation_config={"temperature":0,"response_mime_type":"application/json"})
D="onet/db_31_0_csv/"
occ={r["O*NET-SOC Code"]:r["Title"] for r in csv.DictReader(open(D+"occupation_data.csv",encoding="utf-8"))}
occ_block="\n".join(f"{c} | {t}" for c,t in occ.items())
um=[r["um_title"] for r in csv.DictReader(open("../data/mapping_eval_sample.csv",encoding="utf-8"))]
PROMPT="""You are mapping Malaysian university career titles to occupations in the US O*NET-SOC taxonomy.

For EACH numbered career title below, choose the ONE O*NET occupation (from the list below) whose
main work duties best represent that career. Choose ONLY codes that appear in the list — never invent a code.

If no occupation in the list reasonably represents the career's main duties, answer "NONE" rather than
forcing a weak match.

Give a confidence between 0 and 1 that your chosen occupation (or NONE) is the correct answer.

O*NET OCCUPATIONS (code | title):
{occ_block}

CAREER TITLES:
{titles_block}

Respond with ONLY a JSON object keyed by the career number (as a string):
{{"1": {{"onet_code": "<code from the list, or NONE>", "confidence": 0.0}}, "2": ...}}"""
for b in range(0,len(um),BATCH):
    path=f"gemini_raw/batch_{b//BATCH:02d}.json"
    if os.path.exists(path): continue
    batch=um[b:b+BATCH]
    prompt=PROMPT.format(occ_block=occ_block,titles_block="\n".join(f"{i+1}. {t}" for i,t in enumerate(batch)))
    for delay in [0,20]:
        time.sleep(delay)
        try: resp=model.generate_content(prompt); break
        except ResourceExhausted as e: print("rate limited, backing off",flush=True)
    else: raise SystemExit("gave up on batch "+str(b//BATCH))
    json.dump({"titles":batch,"raw":resp.text,"usage":str(resp.usage_metadata)},open(path,"w",encoding="utf-8"))
    print(f"batch {b//BATCH+1}/{-(-len(um)//BATCH)} done, tokens: {resp.usage_metadata.total_token_count}",flush=True)
    time.sleep(SPACING)
print("ALL DONE")
