from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from scipy.stats import binomtest,spearmanr,wilcoxon
from dgraudit.cli.validate_pattern import benjamini_hochberg

def signed_rank(x):
    x=np.asarray(x,float);x=x[x!=0]
    return (float(wilcoxon(x,alternative='two-sided',method='auto').statistic),float(wilcoxon(x,alternative='two-sided',method='auto').pvalue)) if len(x) else (0.0,1.0)
def rho(x,y):
    if len(set(x))<2 or len(set(y))<2:return (None,None)
    r,p=spearmanr(x,y);return float(r),float(p)
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output');a=p.parse_args();root=(Path('artifacts/runs')/a.run).resolve();d=json.loads((root/'evidence_catalog.json').read_text());edges=sorted({tuple(c['edge']) for c in d['cases']});rows=[]
    for edge in edges:
      all_cases=[c for c in d['cases'] if tuple(c['edge'])==edge];cs=[c for c in all_cases if c['affected_exposed_windows']];mae=[c['metrics']['error_delta_mae'] for c in cs];pred=[c['metrics']['prediction_delta_abs'] for c in cs];base=[c['metrics']['baseline_mae'] for c in cs];wins=[len(c['affected_exposed_windows']) for c in cs];special=[c['metrics']['prediction_delta_abs']-c['metrics']['control_mean_prediction_delta_abs'] for c in cs];_,mae_p=signed_rank(mae);_,special_p=signed_rank(special);pos=sum(x>0 for x in mae);neg=sum(x<0 for x in mae);direction_p=float(binomtest(pos,pos+neg,.5,alternative='two-sided').pvalue) if pos+neg else 1.0
      rows.append({'edge':list(edge),'audited_cases':len(all_cases),'exposed_cases':len(cs),'nonzero_prediction_cases':sum(x>0 for x in pred),'mae_increased':pos,'mae_decreased':neg,'median_prediction_delta_abs':float(np.median(pred)),'median_mae_delta':float(np.median(mae)),'median_focal_minus_control':float(np.median(special)),'tests':{'mae_delta_wilcoxon_p':mae_p,'mae_direction_binomial_p':direction_p,'focal_minus_control_wilcoxon_p':special_p},'correlations':{'mae_delta_vs_baseline_mae':dict(zip(['rho','p'],rho(base,mae))),'mae_delta_vs_prediction_delta':dict(zip(['rho','p'],rho(pred,mae))),'mae_delta_vs_affected_window_count':dict(zip(['rho','p'],rho(wins,mae)))}})
    families=[('mae_delta_wilcoxon_p','mae_delta_wilcoxon_bh'),('mae_direction_binomial_p','mae_direction_binomial_bh'),('focal_minus_control_wilcoxon_p','focal_minus_control_wilcoxon_bh')]
    for raw,adj in families:
      vals=benjamini_hochberg([r['tests'][raw] for r in rows])
      for r,v in zip(rows,vals):r['tests'][adj]=v
    for key in ['mae_delta_vs_baseline_mae','mae_delta_vs_prediction_delta','mae_delta_vs_affected_window_count']:
      valid=[(i,r['correlations'][key]['p']) for i,r in enumerate(rows) if r['correlations'][key]['p'] is not None];adj=benjamini_hochberg([x[1] for x in valid])
      for (i,_),v in zip(valid,adj):rows[i]['correlations'][key]['bh_adjusted_p']=v
    out={'source_run':a.run,'status':'complete','analysis_level':'exploratory edge-level aggregation across predeclared test samples','multiple_comparison_families':'BH separately across four edges for each prespecified test/correlation','edges':rows,'limitations':['Exploratory supplement; does not replace the 160-case family.','Associations are descriptive model-internal relationships, not causal explanations.','Mean edge weight is constant within each edge and was not tested as a within-edge correlate.']}
    text=json.dumps(out,indent=2);print(text)
    if a.output:Path(a.output).write_text(text,encoding='utf-8')
if __name__=='__main__':main()
