import { useEffect, useMemo, useState } from 'react';
import { Activity, ChevronRight, GitBranch, LoaderCircle } from 'lucide-react';
import { loadMsgnetCatalog, type MsgnetCatalog, type MsgnetEdgeImpact } from '@/data/msgnetLoader';

const COLORS = ['#16827f', '#263b59', '#d48b35'];

export function MsgnetWorkspace() {
  const [catalog, setCatalog] = useState<MsgnetCatalog | null>(null);
  const [failure, setFailure] = useState('');
  const [sampleId, setSampleId] = useState(0);
  const [scale, setScale] = useState(0);
  const [variable, setVariable] = useState(6);
  const [edgeKey, setEdgeKey] = useState('');

  useEffect(() => {
    loadMsgnetCatalog().then(setCatalog).catch((error: Error) => setFailure(error.message));
  }, []);

  const sample = catalog?.samples[String(sampleId)];
  const context = sample?.contexts[scale];
  const edges = useMemo(() => {
    if (!sample) return [];
    return sample.edge_impacts
      .filter((edge) => edge.scale_index === scale)
      .sort((a, b) => b.adaptive_weight - a.adaptive_weight);
  }, [sample, scale]);
  const selectedEdge = edges.find((edge) => `${edge.source}-${edge.target}` === edgeKey) ?? edges[0];

  useEffect(() => {
    setEdgeKey('');
  }, [sampleId, scale]);

  if (failure) return <section id="msgnet-workspace" className="border-b border-line bg-[#f7f4ee] px-5 py-16"><div className="mx-auto max-w-[1400px] rounded-xl border border-red-200 bg-white p-6 text-sm text-red-700">{failure}</div></section>;
  if (!catalog || !sample || !context) return <section id="msgnet-workspace" className="flex min-h-[340px] items-center justify-center border-b border-line bg-[#f7f4ee]"><LoaderCircle className="mr-2 animate-spin" size={18}/> Loading audited MSGNet evidence…</section>;

  return (
    <section id="msgnet-workspace" className="border-b border-line bg-[#f7f4ee] px-5 py-16">
      <div className="mx-auto max-w-[1400px]">
        <div className="flex flex-col gap-5 border-b border-[#d8d0c3] pb-7 lg:flex-row lg:items-end lg:justify-between">
          <div><div className="eyebrow">Independent model extension</div><h2 className="mt-2 font-serif text-3xl font-semibold text-[#263b59]">MSGNet scale-graph workspace</h2><p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-ink-500">A separate evidence path for MSGNet on ETTh1. It reuses the site's interaction language without changing the original DGraFormer workspace or its state.</p></div>
          <div className="rounded-lg border border-[#d8d0c3] bg-white px-4 py-3 text-[11px] text-ink-500"><b className="text-[#263b59]">Audited artifact</b><br/>96-step lookback · 96-step forecast · {catalog.case_count} edge interventions</div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[250px_1fr]">
          <aside className="card h-fit space-y-5 p-5 lg:sticky lg:top-5">
            <Control label="Test sample" value={sampleId} options={Object.keys(catalog.samples).map(Number)} render={(v)=>`test ${v}`} onChange={setSampleId}/>
            <Control label="Output variable" value={variable} options={catalog.variables.map((_,i)=>i)} render={(v)=>catalog.variables[v]} onChange={setVariable}/>
            <div><div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ink-400">Scale context</div><div className="grid gap-2">{sample.contexts.map((item,i)=><button key={item.scale_index} onClick={()=>setScale(i)} className={`rounded-lg border px-3 py-3 text-left transition ${scale===i?'border-[#16827f] bg-[#edf7f6]':'border-line bg-white hover:border-[#8ebbb8]'}`}><span className="block text-[12px] font-semibold text-[#263b59]">Scale {i+1} · period {item.period}</span><span className="mt-1 block text-[10px] text-ink-400">FFT {item.fft_strength.toFixed(3)} · contribution {(item.scale_contribution*100).toFixed(1)}%</span></button>)}</div></div>
            <p className="rounded-lg bg-[#f2f4f6] p-3 text-[10px] leading-relaxed text-ink-400">Controls here are local to MSGNet. Changing them does not alter the DGraFormer workspace above.</p>
          </aside>

          <main className="space-y-6">
            <div className="grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
              <Panel eyebrow="Prediction curve" title={`${catalog.variables[variable]} · test ${sampleId}`}><ForecastSvg history={sample.history[variable]} truth={sample.ground_truth[variable]} prediction={sample.prediction[variable]}/><div className="mt-4 flex gap-5 text-[10px] text-ink-400"><Legend color="#8491a5" label="History"/><Legend color="#16827f" label="Ground truth"/><Legend color="#d6453b" label="Prediction" dashed/></div></Panel>
              <Panel eyebrow="Forecast quality" title="Current sample"><div className="grid grid-cols-2 gap-3"><Metric label="MSE" value={sample.metrics.mse.toFixed(4)}/><Metric label="MAE" value={sample.metrics.mae.toFixed(4)}/><Metric label="Period" value={String(context.period)}/><Metric label="Scale contribution" value={`${(context.scale_contribution*100).toFixed(1)}%`}/></div><p className="mt-5 text-[11px] leading-relaxed text-ink-400">These values come from the trained MSGNet checkpoint and stored ETTh1 test outputs; the browser does not run inference.</p></Panel>
            </div>

            <div className="grid gap-6 xl:grid-cols-[.9fr_1.1fr]">
              <Panel eyebrow="Scale graph" title={`Adaptive affinity · scale ${scale+1}`}><Matrix matrix={context.adaptive} variables={catalog.variables} selected={selectedEdge} onPick={(s,t)=>setEdgeKey(`${s}-${t}`)}/><p className="mt-3 text-[10px] text-ink-400">Click a non-diagonal cell to inspect its measured intervention response.</p></Panel>
              <Panel eyebrow="Edge influence" title="Graph weight → intervention evidence"><div className="grid gap-4 md:grid-cols-[.9fr_1.1fr]"><div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">{edges.slice(0,18).map((edge)=><EdgeButton key={`${edge.source}-${edge.target}`} edge={edge} active={edge===selectedEdge} onClick={()=>setEdgeKey(`${edge.source}-${edge.target}`)}/>)}</div>{selectedEdge&&<EdgeDetail edge={selectedEdge}/>}</div></Panel>
            </div>
          </main>
        </div>
      </div>
    </section>
  );
}

function Panel({eyebrow,title,children}:{eyebrow:string;title:string;children:React.ReactNode}){return <article className="card p-5"><div className="text-[10px] font-semibold uppercase tracking-wider text-accent">{eyebrow}</div><h3 className="mt-1 font-serif text-xl font-semibold text-[#263b59]">{title}</h3><div className="mt-5">{children}</div></article>}
function Control({label,value,options,render,onChange}:{label:string;value:number;options:number[];render:(v:number)=>string;onChange:(v:number)=>void}){return <label className="block"><span className="mb-2 block text-[10px] font-semibold uppercase tracking-wider text-ink-400">{label}</span><select value={value} onChange={(e)=>onChange(Number(e.target.value))} className="w-full rounded-lg border border-line bg-white px-3 py-2 text-[12px] text-[#263b59]">{options.map(v=><option key={v} value={v}>{render(v)}</option>)}</select></label>}
function Metric({label,value}:{label:string;value:string}){return <div className="rounded-lg border border-line bg-[#fafbfc] p-3"><div className="text-[9px] uppercase tracking-wider text-ink-400">{label}</div><div className="mt-1 font-mono text-lg font-semibold text-[#263b59]">{value}</div></div>}
function Legend({color,label,dashed=false}:{color:string;label:string;dashed?:boolean}){return <span className="flex items-center gap-2"><i className="w-5 border-t-2" style={{borderColor:color,borderStyle:dashed?'dashed':'solid'}}/>{label}</span>}

function ForecastSvg({history,truth,prediction}:{history:number[];truth:number[];prediction:number[]}){
  const all=[...history,...truth,...prediction], min=Math.min(...all), max=Math.max(...all), range=max-min||1, w=760,h=270,p=18;
  const point=(v:number,i:number,n:number,x0:number,x1:number)=>`${x0+(i/Math.max(1,n-1))*(x1-x0)},${h-p-((v-min)/range)*(h-p*2)}`;
  const historyEnd=w*.48, futureStart=w*.52;
  return <svg viewBox={`0 0 ${w} ${h}`} className="h-[270px] w-full" role="img" aria-label="MSGNet prediction curve"><rect x={futureStart} y="0" width={w-futureStart} height={h} fill="#f5f8f8"/><line x1={futureStart} x2={futureStart} y1="0" y2={h} stroke="#ccd7dc" strokeDasharray="4 5"/><polyline fill="none" stroke="#8491a5" strokeWidth="2" points={history.map((v,i)=>point(v,i,history.length,p,historyEnd)).join(' ')}/><polyline fill="none" stroke="#16827f" strokeWidth="2.2" points={truth.map((v,i)=>point(v,i,truth.length,futureStart,w-p)).join(' ')}/><polyline fill="none" stroke="#d6453b" strokeWidth="2" strokeDasharray="5 4" points={prediction.map((v,i)=>point(v,i,prediction.length,futureStart,w-p)).join(' ')}/></svg>
}

function Matrix({matrix,variables,selected,onPick}:{matrix:number[][];variables:string[];selected?:MsgnetEdgeImpact;onPick:(s:number,t:number)=>void}){
  const max=Math.max(...matrix.flat().filter(Number.isFinite),.001);
  return <div className="grid gap-1" style={{gridTemplateColumns:`52px repeat(${variables.length}, minmax(34px,1fr))`}}><span/>{variables.map(v=><span key={v} className="truncate text-center text-[9px] text-ink-400">{v}</span>)}{matrix.map((row,s)=><div className="contents" key={s}><span className="flex items-center text-[9px] text-ink-400">{variables[s]}</span>{row.map((value,t)=>{const active=selected?.source===s&&selected.target===t;return <button disabled={s===t} onClick={()=>onPick(s,t)} title={`${variables[s]} → ${variables[t]}: ${value.toFixed(4)}`} key={t} className={`aspect-square rounded-sm border transition ${active?'border-[#d6453b] ring-2 ring-[#d6453b]/30':'border-white/50'} ${s===t?'cursor-default':''}`} style={{background:s===t?'#e8edf0':`rgba(22,130,127,${.08+.82*value/max})`}}/>})}</div>)}</div>
}

function EdgeButton({edge,active,onClick}:{edge:MsgnetEdgeImpact;active:boolean;onClick:()=>void}){return <button onClick={onClick} className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left ${active?'border-[#16827f] bg-[#edf7f6]':'border-line hover:border-[#8ebbb8]'}`}><GitBranch size={14} className="shrink-0 text-[#16827f]"/><span className="min-w-0 flex-1 truncate text-[11px] font-semibold text-[#263b59]">{edge.source_name} → {edge.target_name}</span><span className="font-mono text-[10px] text-ink-400">{edge.adaptive_weight.toFixed(3)}</span><ChevronRight size={13}/></button>}
function EdgeDetail({edge}:{edge:MsgnetEdgeImpact}){const supported=edge.statistics.bh_adjusted_p<.05;return <div className="rounded-xl bg-[#263b59] p-5 text-white"><div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-white/60"><Activity size={14}/> Selected edge</div><h4 className="mt-2 font-serif text-2xl font-semibold">{edge.source_name} → {edge.target_name}</h4><div className="mt-5 grid grid-cols-2 gap-3"><DarkMetric label="Graph weight" value={edge.adaptive_weight.toFixed(4)}/><DarkMetric label="Prediction Δ" value={edge.prediction_delta_abs.toFixed(6)}/><DarkMetric label="MAE Δ" value={`${edge.error_delta_mae>=0?'+':''}${edge.error_delta_mae.toFixed(6)}`}/><DarkMetric label="Control mean" value={edge.statistics.control_mean_prediction_delta_abs.toFixed(6)}/><DarkMetric label="Control percentile" value={`${edge.statistics.control_percentile.toFixed(1)}%`}/><DarkMetric label="BH adjusted p" value={edge.statistics.bh_adjusted_p.toFixed(3)}/></div><p className={`mt-5 rounded-lg p-3 text-[10px] leading-relaxed ${supported?'bg-emerald-400/15 text-emerald-100':'bg-amber-300/15 text-amber-100'}`}>{supported?'This edge passes the stored BH-adjusted significance threshold.':'No BH-adjusted support at α=0.05. Treat the response as model-internal exploratory evidence, not causality.'}</p></div>}
function DarkMetric({label,value}:{label:string;value:string}){return <div className="rounded-lg bg-white/8 p-3"><div className="text-[9px] uppercase tracking-wider text-white/50">{label}</div><div className="mt-1 font-mono text-[12px] font-semibold">{value}</div></div>}
