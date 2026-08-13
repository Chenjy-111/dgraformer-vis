import { useMemo, useState } from 'react';
import type { MsgnetCatalog } from '@/data/msgnetLoader';

export function MsgnetGlobalDiagnostic({ catalog, title = 'Remove one relation across all scale graphs' }: { catalog: MsgnetCatalog; title?: string }) {
  const [samplePosition, setSamplePosition] = useState(0);
  const [variable, setVariable] = useState(6);
  const [edgeId, setEdgeId] = useState('0-1');
  const sample = catalog.samples[samplePosition];
  const impacts = useMemo(() => [...sample.global_edge_impacts].sort((a, b) => b.prediction_delta_abs - a.prediction_delta_abs), [sample]);
  const selected = impacts.find((impact) => `${impact.source}-${impact.target}` === edgeId) ?? impacts[0];
  const baseline = sample.prediction[variable];
  const changed = selected.intervention_prediction[variable];
  const truth = sample.ground_truth[variable];
  const extent = [...baseline, ...changed, ...truth];
  const min = Math.min(...extent);
  const max = Math.max(...extent);
  const point = (value: number, step: number) => `${28 + step * (704 / 95)},${172 - ((value - min) / Math.max(max - min, 1e-9)) * 140}`;
  const path = (values: number[]) => values.map((value, step) => `${step ? 'L' : 'M'}${point(value, step)}`).join(' ');

  return <main className="mx-auto max-w-[1240px] space-y-6 px-5 py-10">
    <section className="card overflow-hidden">
      <header className="border-b border-line bg-[#fafbfd] px-5 py-4">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-accent">All-scale intervention · real checkpoint inference</div>
        <h2 className="mt-1 font-serif text-2xl font-semibold text-[#263b59]">{title}</h2>
        <p className="mt-2 text-[11px] text-ink-400">The model is rerun after the same edge is zeroed at every scale. Results are not inferred from scale mixing weights.</p>
      </header>
      <div className="grid gap-3 p-5 sm:grid-cols-4">
        <Metric label="Real inference cases" value={String(catalog.global_case_count)}/>
        <Metric label="Tests × edges" value="5 × 42"/>
        <Metric label="Affected scales" value="3 / 3"/>
        <Metric label="BH-supported" value={String(catalog.global_bh_supported_count)}/>
      </div>
    </section>

    <section className="grid gap-5 lg:grid-cols-[1fr_330px]">
      <div className="space-y-5">
        <section className="card p-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <Selector label="Test sample" value={String(samplePosition)} onChange={value => { setSamplePosition(Number(value)); setEdgeId('0-1'); }} options={catalog.samples.map((item, index) => [String(index), `test ${index} · source index ${item.sample_index}`])}/>
            <Selector label="Displayed variable" value={String(variable)} onChange={value => setVariable(Number(value))} options={catalog.variables.map((name, index) => [String(index), name])}/>
            <Selector label="Directed edge" value={`${selected.source}-${selected.target}`} onChange={setEdgeId} options={impacts.map(impact => [`${impact.source}-${impact.target}`, `${impact.source_name} → ${impact.target_name}`])}/>
          </div>
          <div className="mt-5 grid gap-2 sm:grid-cols-3">
            {impacts.slice(0, 12).map(impact => <button key={`${impact.source}-${impact.target}`} onClick={() => setEdgeId(`${impact.source}-${impact.target}`)} className={`rounded-lg border p-3 text-left ${impact === selected ? 'border-[#16827f] bg-[#edf7f6]' : 'border-line bg-white'}`}>
              <div className="text-[12px] font-semibold">{impact.source_name} → {impact.target_name}</div>
              <div className="mt-1 font-mono text-[9px] text-ink-400">prediction Δ {impact.prediction_delta_abs.toFixed(6)}</div>
            </button>)}
          </div>
          <p className="mt-3 text-[10px] text-ink-400">Showing the 12 largest responses for quick access. All 42 directed edges remain available in the selector.</p>
        </section>

        <section className="card p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2"><div><div className="eyebrow">Stored intervention trajectory</div><h3 className="mt-1 font-serif text-xl font-semibold">{selected.source_name} → {selected.target_name} · {catalog.variables[variable]}</h3></div><span className="font-mono text-[10px] text-ink-400">96 forecast steps</span></div>
          <svg viewBox="0 0 760 200" className="mt-4 w-full rounded-lg border border-line bg-white" role="img" aria-label="Baseline and all-scale edge removal forecast comparison">
            {[0,1,2,3,4].map(i => <line key={i} x1="28" x2="732" y1={32+i*35} y2={32+i*35} stroke="#e6eaee"/>) }
            <path d={path(truth)} fill="none" stroke="#202c3b" strokeWidth="2"/>
            <path d={path(baseline)} fill="none" stroke="#2779bd" strokeWidth="2"/>
            <path d={path(changed)} fill="none" stroke="#d45b45" strokeWidth="2" strokeDasharray="5 3"/>
          </svg>
          <div className="mt-3 flex flex-wrap gap-5 text-[10px] text-ink-500"><Key color="#202c3b" label="Ground truth"/><Key color="#2779bd" label="Baseline"/><Key color="#d45b45" label="All-scale edge removed" dashed/></div>
        </section>
      </div>

      <aside className="card h-fit overflow-hidden lg:sticky lg:top-5">
        <header className="bg-[#263b59] px-5 py-4 text-white"><div className="text-[9px] uppercase tracking-wider text-white/60">All-scale evidence rail</div><h3 className="mt-1 font-serif text-xl font-semibold">{selected.source_name} → {selected.target_name}</h3></header>
        <div className="grid gap-4 p-5">
          <Metric label="Scale weights (1 / 2 / 3)" value={selected.scale_weights.map(v => v.toFixed(4)).join(' / ')}/>
          <Metric label="Mean absolute prediction Δ" value={selected.prediction_delta_abs.toFixed(6)}/>
          <Metric label="Maximum prediction Δ" value={selected.prediction_delta_max.toFixed(6)}/>
          <Metric label="MAE Δ" value={signed(selected.error_delta_mae)}/>
          <Metric label="MSE Δ" value={signed(selected.error_delta_mse)}/>
          <Metric label="Control mean" value={selected.statistics.control_mean_prediction_delta_abs.toFixed(6)}/>
          <Metric label="Empirical / BH p" value={`${selected.statistics.empirical_p.toFixed(3)} / ${selected.statistics.bh_adjusted_p.toFixed(3)}`}/>
          <Metric label="Bootstrap 95% CI" value={selected.statistics.candidate_minus_control_mean_bootstrap_ci_95.map(v => signed(v)).join(' to ')}/>
        </div>
        <div className="border-t border-line bg-amber-50 px-5 py-4 text-[10px] leading-relaxed text-amber-800">This is a model-internal sensitivity result for one checkpoint and sample. It is not evidence of real-world causality.</div>
      </aside>
    </section>
  </main>;
}

function Selector({label,value,onChange,options}:{label:string;value:string;onChange:(value:string)=>void;options:string[][]}) { return <label><span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-ink-400">{label}</span><select className="w-full rounded-lg border border-line bg-white px-3 py-2 text-[12px]" value={value} onChange={event=>onChange(event.target.value)}>{options.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label> }
function Metric({label,value}:{label:string;value:string}) { return <div><div className="text-[9px] uppercase tracking-wider text-ink-400">{label}</div><div className="mt-1 break-all font-mono text-[11px] font-semibold text-[#263b59]">{value}</div></div> }
function Key({color,label,dashed=false}:{color:string;label:string;dashed?:boolean}) { return <span className="flex items-center gap-2"><i className="w-5 border-t-2" style={{borderColor:color,borderStyle:dashed?'dashed':'solid'}}/>{label}</span> }
const signed=(value:number)=>`${value>0?'+':''}${value.toFixed(6)}`;
