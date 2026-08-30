from __future__ import annotations
import argparse, hashlib, json, platform
from pathlib import Path
import numpy as np
import torch
from dgraudit.adapters import DGraFormerAdapter
from dgraudit.cli.validate_pattern import benjamini_hochberg, empirical_p_plus_one, impact_metrics, sha256

def canonical(v): return json.dumps(v, sort_keys=True, separators=(",", ":"))

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--registry",default="configs/phase1_registry.json");p.add_argument("--output-root",default="artifacts/runs");a=p.parse_args()
    cp,rp=Path(a.config).resolve(),Path(a.registry).resolve();cfg=json.loads(cp.read_text());reg=json.loads(rp.read_text());dataset_name=cfg["dataset"];ds=reg["datasets"][dataset_name];root=Path(reg["source_root"]);checkpoint=root/"checkpoints"/ds["setting"]/"checkpoint.pth";data=root/ds["root_path"]/ds["data_path"]
    fingerprints=[sha256(x) for x in [cp,rp,checkpoint,data,Path(__file__).resolve(),Path(__file__).resolve().parents[1]/"adapters.py"]];run_id=hashlib.sha256("|".join(fingerprints).encode()).hexdigest();out=Path(a.output_root).resolve()/run_id
    for name in ["predictions","controls","evidence"]:(out/name).mkdir(parents=True,exist_ok=True)
    adapter=DGraFormerAdapter(str(root),dataset_name,reg["common"],ds,reg["random_seed"]);adapter.load_checkpoint(str(checkpoint));stages=adapter.extract_graph_stages({"current_epoch":cfg["current_epoch"]})["windows"]
    relations=[]
    for s in range(ds["n_vars"]):
      for t in range(ds["n_vars"]):
        if s==t:continue
        weights=[float(w["normalized"][s,t]) for w in stages];active=[i for i,v in enumerate(weights) if v>0]
        if active:relations.append({"edge":[s,t],"windows":active,"mean_weight":float(np.mean([weights[i] for i in active]))})
    focal={tuple(x) for x in cfg["candidate_edges"]};records=[]
    for sample in cfg["samples"]:
      batch=dict(adapter.load_sample("test",sample));batch["current_epoch"]=cfg["current_epoch"];baseline=adapter.predict(batch);truth=torch.as_tensor(batch["y"][-reg["common"]["pred_len"]:,:],dtype=torch.float32).unsqueeze(0);exposure=sorted(set((torch.as_tensor(batch["time_index"])%len(stages)).reshape(-1).tolist()))
      predictions={};metrics={}
      for rel in relations:
        e=tuple(rel["edge"]);result=adapter.predict_with_graph_override(batch,{"type":"global_structural_edge_removal","source":e[0],"target":e[1],"current_epoch":cfg["current_epoch"]});predictions[e]=result["prediction"];metrics[e]=impact_metrics(baseline,result["prediction"],truth)
      for e in sorted(focal):
        rel=next(x for x in relations if tuple(x["edge"])==e);eligible=[x for x in relations if tuple(x["edge"])!=e];eligible.sort(key=lambda x:(abs(len(x["windows"])-len(rel["windows"])),abs(x["mean_weight"]-rel["mean_weight"]),x["edge"]));pool=eligible[:cfg["control_matching"]["nearest_relations"]];seed=cfg["control_matching"]["random_seed"]+len(records);rng=np.random.default_rng(seed);sampled=[pool[int(rng.integers(0,len(pool)))] for _ in range(cfg["control_matching"]["repetitions"])];imp=np.asarray([metrics[tuple(x["edge"])]["prediction_delta_abs"] for x in sampled]);fm=metrics[e];emp=empirical_p_plus_one(imp,fm["prediction_delta_abs"]);pct=float(100*np.mean(imp<fm["prediction_delta_abs"])+50*np.mean(imp==fm["prediction_delta_abs"]));br=np.random.default_rng(seed+100000);dist=fm["prediction_delta_abs"]-br.choice(imp,size=(cfg["bootstrap_repetitions"],len(imp)),replace=True).mean(1);alpha=1-cfg["confidence_level"]
        pred_path=out/"predictions"/f"s{sample}_e{e[0]}_{e[1]}.npz";np.savez_compressed(pred_path,baseline=baseline.numpy()[0],intervention=predictions[e].numpy()[0],truth=truth.numpy()[0]);controls=[{"edge":x["edge"],"windows":x["windows"],"mean_weight":x["mean_weight"],"prediction_delta_abs":metrics[tuple(x["edge"])]["prediction_delta_abs"]} for x in sampled];control_path=out/"controls"/f"s{sample}_e{e[0]}_{e[1]}.json";control_path.write_text(json.dumps(controls,indent=2))
        records.append({"id":f"{dataset_name.lower()}_global_s{sample}_edge_{e[0]}_{e[1]}","sample":sample,"edge":list(e),"retained_windows":rel["windows"],"exposed_windows":exposure,"affected_exposed_windows":sorted(set(rel["windows"])&set(exposure)),"mean_weight":rel["mean_weight"],"metrics":{**fm,"control_mean_prediction_delta_abs":float(imp.mean()),"control_percentile_midrank":pct,"empirical_p":emp,"bh_adjusted_p":None,"effect_difference_bootstrap_ci":np.quantile(dist,[alpha/2,1-alpha/2]).tolist()},"prediction_file":str(pred_path.relative_to(out)),"controls_file":str(control_path.relative_to(out)),"control_seed":seed})
    adjusted=benjamini_hochberg([x["metrics"]["empirical_p"] for x in records])
    for x,v in zip(records,adjusted):x["metrics"]["bh_adjusted_p"]=v;(out/"evidence"/f'{x["id"]}.json').write_text(json.dumps(x,indent=2))
    catalog={"run_id":run_id,"status":"complete","dataset":dataset_name,"protocol":"global_structural_edge_removal","schedule":{"state":"final","current_epoch_equivalent":5,"static_weight":.1,"learned_weight":.9},"case_count":len(records),"cases":records,"cross_run":{"status":"missing","metrics":None,"reason":f"Only one real {dataset_name} checkpoint is available."}}
    (out/"evidence_catalog.json").write_text(json.dumps(catalog,indent=2));manifest={"run_id":run_id,"status":"complete","case_count":len(records),"checkpoint_sha256":sha256(checkpoint),"data_sha256":sha256(data),"config_sha256":sha256(cp),"catalog_sha256":sha256(out/"evidence_catalog.json"),"environment":{"python":platform.python_version(),"torch":torch.__version__,"cuda":torch.version.cuda}}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
