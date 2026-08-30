from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np

VARIABLES=["HUFL","HULL","MUFL","MULL","LUFL","LULL","OT"]

def main():
    p=argparse.ArgumentParser();p.add_argument("--run",required=True);p.add_argument("--output",default="legacy/v1/artifacts/public-data/evidence/etth1_global_intervention_catalog.json");a=p.parse_args()
    root=Path("artifacts/runs")/a.run;catalog=json.loads((root/"evidence_catalog.json").read_text())
    cases=[]
    for c in catalog["cases"]:
        arrays=np.load(root/c["prediction_file"]);baseline=arrays["baseline"];intervention=arrays["intervention"];truth=arrays["truth"]
        delta=np.abs(intervention-baseline);ranking=[]
        for i,name in enumerate(VARIABLES):
            series=delta[:,i];ranking.append({"variable":name,"mean_absolute_prediction_delta":float(series.mean()),"max_absolute_prediction_delta":float(series.max()),"peak_step":int(series.argmax()+1)})
        ranking.sort(key=lambda x:(-x["mean_absolute_prediction_delta"],x["variable"]))
        cases.append({**c,"baseline_prediction":baseline.tolist(),"intervention_prediction":intervention.tolist(),"ground_truth":truth.tolist(),"variable_ranking":ranking})
    dataset=catalog["dataset"];output={"run_id":catalog["run_id"],"dataset":dataset,"protocol":catalog["protocol"],"schedule":catalog["schedule"],"variables":VARIABLES,"samples":sorted({c["sample"] for c in cases}),"edges":sorted({tuple(c["edge"]) for c in cases}),"cases":cases,"cross_run":catalog["cross_run"],"notice":f"All displayed values are stored outputs from the real {dataset} checkpoint. The browser does not rerun the model."}
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(output,separators=(",",":")),encoding="utf-8");print(json.dumps({"output":str(path),"cases":len(cases)}))
if __name__=="__main__":main()
