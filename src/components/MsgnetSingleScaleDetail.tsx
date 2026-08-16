import { useMemo, useState } from 'react';
import type { MsgnetCatalog } from '@/data/msgnetLoader';
import { EdgeMatrixFigure, ImpactBars } from './MsgnetDiagnosticCharts';

export function MsgnetSingleScaleDetail({catalog}:{catalog:MsgnetCatalog}) {
  const [samplePosition,setSamplePosition]=useState(0),[scale,setScale]=useState(0),[edgeId,setEdgeId]=useState(''),[variable,setVariable]=useState(6);
  const sample=catalog.samples[samplePosition];
  const rows=useMemo(()=>sample.edge_impacts.filter(item=>item.scale_index===scale).sort((a,b)=>b.prediction_delta_abs-a.prediction_delta_abs),[sample,scale]);
  const selected=rows.find(item=>`${item.source}-${item.target}`===edgeId)??rows[0];
  const across=catalog.samples.map((item,index)=>({index,sampleIndex:item.sample_index,impact:item.edge_impacts.find(value=>value.scale_index===scale&&value.source===selected.source&&value.target===selected.target)}));
  const context=sample.contexts[scale];
  return <main className="mx-auto max-w-[1240px] space-y-5 px-5 py-10">
    <section className="card grid gap-4 p-5 md:grid-cols-4">
      <Choice label="Test sample" value={String(samplePosition)} change={value=>{setSamplePosition(+value);setEdgeId('')}} options={catalog.samples.map((item,index)=>[String(index),`ETTh1 · test ${item.sample_index}`])}/>
      <Choice label="Single window (MSGNet scale)" value={String(scale)} change={value=>{setScale(+value);setEdgeId('')}} options={sample.contexts.map((item,index)=>[String(index),`Window ${index} · scale ${index+1} · period ${item.period}`])}/>
      <Choice label="Directed edge" value={`${selected.source}-${selected.target}`} change={setEdgeId} options={rows.map(item=>[`${item.source}-${item.target}`,`${item.source_name} → ${item.target_name}`])}/>
      <Choice label="Output variable" value={String(variable)} change={value=>setVariable(+value)} options={catalog.variables.map((name,index)=>[String(index),name])}/>
    </section>

    <section className="card p-5">
      <h3 className="font-serif text-xl font-semibold text-[#263b59]">Single-window response across audited tests</h3>
      <p className="mt-1 text-[11px] text-ink-400">MSGNet has no temporal graph windows; the equivalent intervention unit is one scale graph. Window {scale} below means scale {scale+1}, period {context.period}.</p>
      <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[650px] text-left text-[11px]"><thead className="text-ink-400"><tr><th className="p-2">Test</th><th>Prediction Δ</th><th>MAE Δ</th><th>Control mean</th><th>BH adjusted p</th></tr></thead><tbody>{across.map(row=><tr key={row.sampleIndex} onClick={()=>setSamplePosition(row.index)} className={`cursor-pointer border-t border-line ${row.index===samplePosition?'bg-[#edf6f5]':''}`}><td className="p-2 font-semibold">test {row.sampleIndex}</td><td className="font-mono">{row.impact?.prediction_delta_abs.toFixed(6)??'—'}</td><td className="font-mono">{row.impact?signed(row.impact.error_delta_mae):'—'}</td><td className="font-mono">{row.impact?.statistics.control_mean_prediction_delta_abs.toFixed(6)??'—'}</td><td className="font-mono">{row.impact?.statistics.bh_adjusted_p.toFixed(3)??'—'}</td></tr>)}</tbody></table></div>
      <div className="mt-5 grid gap-5 border-t border-line pt-5 lg:grid-cols-[1fr_1.2fr]"><div><div className="eyebrow mb-3">Selected edge in scale graph</div><EdgeMatrixFigure matrix={context.adaptive} names={catalog.variables} source={selected.source} target={selected.target}/></div><div><div className="eyebrow mb-3">Cross-test intervention response</div><ImpactBars items={across.flatMap(row=>row.impact?[row.impact]:[])} selected={selected}/></div></div>
    </section>

    <section className="card overflow-hidden"><header className="border-b border-line bg-[#fafbfd] px-5 py-4"><div className="text-[10px] font-semibold uppercase tracking-wider text-accent">Single-scale structural intervention</div><h3 className="mt-1 font-serif text-2xl font-semibold text-[#263b59]">{selected.source_name} → {selected.target_name} · test {sample.sample_index}</h3></header><div className="grid gap-3 p-5 sm:grid-cols-4"><Mini label="Window / scale / period" value={`${scale} / ${scale+1} / ${context.period}`}/><Mini label="Graph weight" value={selected.adaptive_weight.toFixed(6)}/><Mini label="Prediction Δ" value={selected.prediction_delta_abs.toFixed(6)}/><Mini label="MAE Δ" value={signed(selected.error_delta_mae)}/><Mini label="Control mean" value={selected.statistics.control_mean_prediction_delta_abs.toFixed(6)}/><Mini label="Control percentile" value={`${selected.statistics.control_percentile.toFixed(2)}%`}/><Mini label="Empirical p" value={selected.statistics.empirical_p.toFixed(3)}/><Mini label="BH adjusted p" value={selected.statistics.bh_adjusted_p.toFixed(3)}/></div><div className="border-t border-line px-5 py-4 text-[11px] leading-relaxed text-ink-500">Removing this edge only from scale {scale+1} changed the complete 96 × 7 prediction tensor by a mean absolute value of {selected.prediction_delta_abs.toFixed(6)}. This is checkpoint-internal intervention evidence, not a causal claim. The selected display variable is {catalog.variables[variable]}.</div></section>
  </main>
}

function Choice({label,value,change,options}:{label:string;value:string;change:(value:string)=>void;options:string[][]}){return <label><span className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-ink-400">{label}</span><select className="w-full rounded-lg border border-[#cad4df] bg-white px-3 py-2.5 text-[12px] font-semibold" value={value} onChange={event=>change(event.target.value)}>{options.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>}
function Mini({label,value}:{label:string;value:string}){return <div className="rounded-lg bg-[#f5f7fa] p-3"><div className="text-[9px] uppercase tracking-wider text-ink-400">{label}</div><div className="mt-1 font-mono text-[11px] font-semibold text-ink-800">{value}</div></div>}
const signed=(value:number)=>`${value>0?'+':''}${value.toFixed(6)}`;
