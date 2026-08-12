from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import torch
from dgraudit.adapters import DGraFormerAdapter
from dgraudit.cli.validate_pattern import impact_metrics

AUDIT_CASES=[(0,(0,2)),(928,(0,3)),(1785,(0,4)),(2784,(5,4))]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--config',required=True);p.add_argument('--registry',default='configs/phase1_registry.json');a=p.parse_args()
    root=(Path('artifacts/runs')/a.run).resolve();config_path=Path(a.config).resolve();registry_path=Path(a.registry).resolve();catalog=json.loads((root/'evidence_catalog.json').read_text());cfg=json.loads(config_path.read_text());reg=json.loads(registry_path.read_text());ds=reg['datasets']['ETTh1'];adapter=DGraFormerAdapter(reg['source_root'],'ETTh1',reg['common'],ds,reg['random_seed']);checkpoint=Path(reg['source_root'])/'checkpoints'/ds['setting']/'checkpoint.pth';adapter.load_checkpoint(str(checkpoint));stages=adapter.extract_graph_stages({'current_epoch':cfg['current_epoch']})['windows']
    relations=[]
    for s in range(ds['n_vars']):
      for t in range(ds['n_vars']):
        if s==t:continue
        weights=[float(w['normalized'][s,t]) for w in stages];active=[i for i,v in enumerate(weights) if v>0]
        if active:relations.append({'edge':(s,t),'windows':active,'mean_weight':float(np.mean([weights[i] for i in active]))})
    report=[]
    for sample,edge in AUDIT_CASES:
      record=next(x for x in catalog['cases'] if x['sample']==sample and tuple(x['edge'])==edge);batch=dict(adapter.load_sample('test',sample));batch['current_epoch']=cfg['current_epoch'];baseline=adapter.predict(batch);identity=adapter.predict_with_graph_override(batch,{'type':'identity','window':0,'current_epoch':cfg['current_epoch']})['prediction'];outcome=adapter.predict_with_graph_override(batch,{'type':'global_structural_edge_removal','source':edge[0],'target':edge[1],'current_epoch':cfg['current_epoch']});intervention=outcome['prediction'];truth=torch.as_tensor(batch['y'][-reg['common']['pred_len']:,:],dtype=torch.float32).unsqueeze(0);prediction_path=root/Path(record['prediction_file'].replace('\\','/'));assert prediction_path.is_file(),prediction_path;stored=np.load(prediction_path);metrics=impact_metrics(baseline,intervention,truth)
      exposure=sorted(set((torch.as_tensor(batch['time_index'])%len(stages)).reshape(-1).tolist()));rel=next(x for x in relations if x['edge']==edge);affected=sorted(set(exposure)&set(rel['windows']))
      eligible=[x for x in relations if x['edge']!=edge];eligible.sort(key=lambda x:(abs(len(x['windows'])-len(rel['windows'])),abs(x['mean_weight']-rel['mean_weight']),x['edge']));pool=eligible[:cfg['control_matching']['nearest_relations']];rng=np.random.default_rng(record['control_seed']);expected_edges=[pool[int(rng.integers(0,len(pool)))]['edge'] for _ in range(cfg['control_matching']['repetitions'])];stored_controls=json.loads((root/record['controls_file']).read_text());stored_edges=[tuple(x['edge']) for x in stored_controls]
      control_cache={}
      max_control_delta=0.0
      for item in stored_controls:
        e=tuple(item['edge'])
        if e not in control_cache:
          pred=adapter.predict_with_graph_override(batch,{'type':'global_structural_edge_removal','source':e[0],'target':e[1],'current_epoch':cfg['current_epoch']})['prediction'];control_cache[e]=impact_metrics(baseline,pred,truth)['prediction_delta_abs']
        max_control_delta=max(max_control_delta,abs(control_cache[e]-item['prediction_delta_abs']))
      checks={'identity_max_abs':float((identity-baseline).abs().max()),'baseline_array_max_abs':float(np.max(np.abs(stored['baseline']-baseline.numpy()[0]))),'intervention_array_max_abs':float(np.max(np.abs(stored['intervention']-intervention.numpy()[0]))),'truth_array_max_abs':float(np.max(np.abs(stored['truth']-truth.numpy()[0]))),'prediction_metric_abs_diff':abs(metrics['prediction_delta_abs']-record['metrics']['prediction_delta_abs']),'mae_delta_abs_diff':abs(metrics['error_delta_mae']-record['metrics']['error_delta_mae']),'exposure_exact':exposure==record['exposed_windows'],'affected_exact':affected==record['affected_exposed_windows'],'control_edge_sequence_exact':expected_edges==stored_edges,'control_value_max_abs_diff':max_control_delta}
      passed=all(v is True or (isinstance(v,float) and v==0.0) for v in checks.values());report.append({'id':record['id'],'passed':passed,'checks':checks})
    print(json.dumps({'run_id':a.run,'audit_cases':len(report),'all_passed':all(x['passed'] for x in report),'results':report},indent=2))
    return 0 if all(x['passed'] for x in report) else 1
if __name__=='__main__':raise SystemExit(main())
