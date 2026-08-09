import { useEffect, useState, type ReactNode } from 'react';
import { CheckCircle2, CircleDashed, Clipboard, Download, ExternalLink, FileCode2, FlaskConical, GitCompareArrows, Route, ShieldCheck } from 'lucide-react';
import { Section } from './layout/Section';
import { useDemoStore } from '@/store/useDemoStore';
import { copyText } from '@/engine/narrativeGenerator';

interface Evidence {
  conclusion_id: string;
  run_id: string; dataset: string; sample_index: number; window: number;
  edge: { source_name: string; target_name: string; topk_score: number; retained_edge_rank: number };
  focal_metrics: { baseline_mae: number; intervention_mae: number; prediction_delta_abs: number; error_delta_mae: number };
  weight_impact: { edge_count: number; spearman_rho: number; spearman_p: number; k: number; overlap_at_k: number };
  controls: { repetitions: number; control_mean_prediction_delta_abs: number; control_percentile: number; empirical_p: number; bh_adjusted_p: number; standardized_effect_size: number; effect_difference_bootstrap_ci: [number, number] };
  identity_override_max_absolute_difference: number;
  schedule: { state: string; current_epoch_equivalent: number; static_weight: number; learned_weight: number };
  provenance: { data_sha256: string; checkpoint_sha256: string; config_sha256: string; test_input_time: [string,string]; forecast_time: [string,string] };
  reproduction: { command: string; manifest: string; environment: string; stdout: string; stderr: string; raw_operands: string[]; formula_ids: string[]; code_references: string[] };
  conclusion: string;
}

const EVIDENCE_URL = `${import.meta.env.BASE_URL}data/evidence/phase5_etth2_s0_w0_edge_1_5.json`;

export function EvidenceValidation() {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState(false);
  const setCase = useDemoStore((s) => s.setCase);
  const setStore = useDemoStore((s) => s.set);
  useEffect(() => { fetch(EVIDENCE_URL).then((r) => { if (!r.ok) throw new Error(); return r.json(); }).then(setEvidence).catch(() => setError(true)); }, []);

  const openAuditedCandidate = () => {
    setCase({ dataset: 'ETTh2', sampleId: 0, horizon: 96, target: 5 });
    setStore('view', 'graph');
    setStore('graphLayout', 'matrix');
    setStore('graphSource', 'sparse');
    setStore('windowIdx', 0);
    setStore('selectedEdge', { source: 1, target: 5 });
    document.querySelector('#workspace')?.scrollIntoView({ behavior: 'smooth' });
  };

  return <>
    <Section id="evidence" eyebrow="Evidence validation · Phase 5" title="A high graph weight did not imply high functional impact" intro="We removed the predeclared ETTh2 candidate inside the real message-passing path, reran the checkpoint, and compared its effect with 100 same-window real-edge controls. The negative result is retained." className="bg-[#f7f9fb]">
      {error && <div className="card border-red-200 p-5 text-sm text-red-700">Evidence unavailable. No substitute result was generated.</div>}
      {!evidence && !error && <div className="card p-5 text-sm text-ink-400">Loading audited evidence…</div>}
      {evidence && <div className="space-y-5">
        <div className="card overflow-hidden border-[#cbd8e5]">
          <div className="flex flex-col gap-4 bg-[#263b59] px-5 py-4 text-white lg:flex-row lg:items-center lg:justify-between">
            <div><div className="text-[10px] font-semibold uppercase tracking-[.16em] text-[#aebed2]">Active audited case</div><div className="mt-1 text-[14px] font-semibold">{evidence.conclusion_id} · {evidence.dataset} / sample {evidence.sample_index} / window {evidence.window} / {evidence.edge.source_name}→{evidence.edge.target_name}</div></div>
            <button onClick={openAuditedCandidate} className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-4 py-2 text-[12px] font-semibold text-[#263b59] transition hover:bg-[#edf3f8]"><ExternalLink size={14}/>Open candidate in graph workspace</button>
          </div>
          <nav aria-label="Audited evidence journey" className="grid grid-cols-2 border-t border-white/10 bg-white md:grid-cols-5">
            {[['Discover','#workspace'],['Intervene','#observed-intervention'],['Validate','#evidence-metrics'],['Cross-run','#cross-run'],['Trace','#reproduction-trace']].map(([label,href], index)=><a key={label} href={href} className="flex items-center gap-2 border-b border-r border-line px-4 py-3 text-[11.5px] font-semibold text-ink-500 transition hover:bg-[#f3f7fa] hover:text-accent"><span className="data-num text-accent">0{index+1}</span>{label}</a>)}
          </nav>
        </div>
        <div className="flex flex-wrap gap-2"><Status icon={<ShieldCheck size={14}/>} text="Real checkpoint forward"/><Status icon={<FlaskConical size={14}/>} text={`${evidence.controls.repetitions} real-edge controls`}/><Status icon={<CheckCircle2 size={14}/>} text={`Identity Δmax = ${evidence.identity_override_max_absolute_difference.toFixed(1)}`}/></div>
        <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <article id="observed-intervention" className="card scroll-mt-6 p-6">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="eyebrow">Observed intervention</div><h3 className="mt-1 text-[21px] font-semibold">{evidence.edge.source_name} → {evidence.edge.target_name}</h3><p className="mt-1 text-[12.5px] text-ink-400">{evidence.dataset} · test sample {evidence.sample_index} · window {evidence.window} · retained rank {evidence.edge.retained_edge_rank}</p></div><span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-semibold text-amber-800">Candidate Pattern</span></div>
            <div className="mt-6 space-y-4"><ImpactBar label="Candidate edge removal" value={evidence.focal_metrics.prediction_delta_abs} max={evidence.controls.control_mean_prediction_delta_abs} color="bg-[#d6453b]"/><ImpactBar label="Matched-control mean" value={evidence.controls.control_mean_prediction_delta_abs} max={evidence.controls.control_mean_prediction_delta_abs} color="bg-[#16827f]"/></div>
            <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4"><Metric label="Prediction Δ" value={fmt(evidence.focal_metrics.prediction_delta_abs)}/><Metric label="MAE before" value={fmt(evidence.focal_metrics.baseline_mae)}/><Metric label="MAE after" value={fmt(evidence.focal_metrics.intervention_mae)}/><Metric label="MAE Δ" value={signed(evidence.focal_metrics.error_delta_mae)}/></div>
          </article>
          <article className="rounded-xl border border-[#d6e5e4] bg-[#edf6f5] p-6"><div className="eyebrow">Matched-control verdict</div><div className="mt-3 font-serif text-[34px] font-semibold text-[#175d5b]">25th <span className="text-[16px] font-normal">percentile</span></div><p className="mt-3 text-[13.5px] leading-relaxed text-ink-700">The candidate effect was smaller than most matched controls. Empirical p = <b>{evidence.controls.empirical_p.toFixed(3)}</b>; BH-adjusted p = <b>{evidence.controls.bh_adjusted_p.toFixed(3)}</b>.</p><div className="mt-4 border-t border-[#cfe0df] pt-4 text-[12px] leading-relaxed text-ink-500">Effect difference 95% bootstrap CI<br/><span className="data-num text-ink-900">[{fmt(evidence.controls.effect_difference_bootstrap_ci[0])}, {fmt(evidence.controls.effect_difference_bootstrap_ci[1])}]</span></div></article>
        </div>
        <div id="evidence-metrics" className="grid scroll-mt-6 gap-4 md:grid-cols-3"><MetricCard title="Weight ↔ impact" value={`ρ = ${evidence.weight_impact.spearman_rho.toFixed(3)}`} note={`p = ${evidence.weight_impact.spearman_p.toFixed(3)} across ${evidence.weight_impact.edge_count} retained edges`}/><MetricCard title={`Overlap@${evidence.weight_impact.k}`} value={`${Math.round(evidence.weight_impact.overlap_at_k*100)}%`} note="Only one top-five weight edge was also a top-five impact edge."/><MetricCard title="Standardized effect" value={evidence.controls.standardized_effect_size.toFixed(3)} note="Candidate impact minus control mean, divided by control standard deviation."/></div>
        <div className="rounded-xl border-l-4 border-[#263b59] bg-white p-5 shadow-sm"><div className="text-[12px] font-semibold uppercase tracking-[.12em] text-ink-400">Supported conclusion</div><p className="mt-2 text-[14px] leading-relaxed text-ink-700">{evidence.conclusion}</p></div>
        <ReproductionTrace evidence={evidence}/>
      </div>}
    </Section>
    <Section id="cross-run" eyebrow="Cross-run validation · Future extension" title="Not evaluated — one real checkpoint is available" intro="Cross-training reproducibility requires at least three independently trained checkpoints. The missing evidence limits the claim, but does not block the completed single-checkpoint workflow.">
      <div className="grid gap-4 md:grid-cols-[0.8fr_1.2fr]"><div className="rounded-xl border border-dashed border-[#b9c5d3] bg-[#f7f9fb] p-6"><div className="flex items-center gap-2 text-ink-700"><CircleDashed size={18}/><b className="text-sm">Status: Not evaluated</b></div><p className="mt-3 text-[13px] leading-relaxed text-ink-500">No simulated checkpoints, Jaccard values, recurrence rates, or stability scores were generated.</p></div><div className="card grid gap-3 p-5 sm:grid-cols-2">{['Checkpoint performance screening','Graph-edge Jaccard','Edge recurrence frequency','Intervention direction consistency'].map((item)=><div key={item} className="flex items-center gap-2 rounded-lg bg-[#f5f7fa] p-3 text-[12.5px] text-ink-500"><GitCompareArrows size={15} className="text-ink-400"/>{item}<span className="ml-auto data-num text-ink-400">null</span></div>)}</div></div>
    </Section>
    <Section id="workflow" eyebrow="Audited workflow" title="From candidate discovery to reproducible evidence" intro="The current system completes the main single-checkpoint path. Cross-run comparison remains a clearly separated future extension." className="bg-[#f7f9fb]">
      <ol className="grid gap-3 md:grid-cols-5">{[['01','Select','Choose a real dataset and test sample.'],['02','Discover','Inspect candidate edges, roles and local patterns.'],['03','Intervene','Modify the graph window and rerun the checkpoint.'],['04','Validate','Compare with matched real-edge controls.'],['05','Trace','Inspect hashes, operands, commands and evidence.']].map(([i,t,b])=><li key={i} className="card p-4"><span className="data-num text-[11px] text-accent">{i}</span><h3 className="mt-2 text-[15px] font-semibold">{t}</h3><p className="mt-2 text-[12.5px] leading-relaxed text-ink-500">{b}</p></li>)}</ol>
    </Section>
  </>;
}

function ReproductionTrace({ evidence }: { evidence: Evidence }) {
  return <article id="reproduction-trace" className="card scroll-mt-6 overflow-hidden">
    <div className="border-b border-line bg-[#f6f8fb] px-6 py-5"><div className="flex items-center gap-2 text-[#263b59]"><Route size={18}/><h3 className="text-[17px] font-semibold">Reproduction Trace</h3></div><p className="mt-2 text-[12.5px] leading-relaxed text-ink-500">Every displayed value below resolves to the same completed run. Paths identify audited repository artifacts; the static website does not rerun the checkpoint.</p></div>
    <div className="grid gap-0 lg:grid-cols-[0.9fr_1.1fr]">
      <div className="space-y-4 border-b border-line p-6 lg:border-b-0 lg:border-r">
        <div className="eyebrow">Identity & provenance</div>
        <dl className="space-y-2.5 text-[11px] text-ink-500"><Trace label="Run ID" value={evidence.run_id}/><Trace label="Checkpoint" value={evidence.provenance.checkpoint_sha256}/><Trace label="Dataset" value={evidence.provenance.data_sha256}/><Trace label="Config" value={evidence.provenance.config_sha256}/></dl>
        <div className="rounded-lg bg-[#f5f7fa] p-3 text-[11px] leading-relaxed text-ink-500"><b className="text-ink-700">Canonical schedule:</b> epoch-equivalent {evidence.schedule.current_epoch_equivalent} · {evidence.schedule.static_weight} static + {evidence.schedule.learned_weight} learned<br/><b className="text-ink-700">Input:</b> {evidence.provenance.test_input_time.join(' → ')}<br/><b className="text-ink-700">Forecast:</b> {evidence.provenance.forecast_time.join(' → ')}</div>
      </div>
      <div className="space-y-5 p-6">
        <TraceGroup icon={<FileCode2 size={15}/>} title="Raw operands" items={evidence.reproduction.raw_operands}/>
        <TraceGroup icon={<FlaskConical size={15}/>} title="Formula IDs" items={evidence.reproduction.formula_ids}/>
        <TraceGroup icon={<FileCode2 size={15}/>} title="Code references" items={evidence.reproduction.code_references}/>
        <div><div className="mb-2 flex items-center justify-between gap-3"><span className="text-[11px] font-semibold uppercase tracking-[.1em] text-ink-400">Reproduction command</span><button onClick={() => copyText(evidence.reproduction.command)} className="inline-flex items-center gap-1 text-[11px] font-semibold text-accent hover:underline"><Clipboard size={12}/>Copy</button></div><code className="block overflow-x-auto rounded-lg bg-[#18283d] p-3 text-[10.5px] leading-relaxed text-[#d9e4ef]">{evidence.reproduction.command}</code></div>
        <div className="flex flex-wrap gap-3"><a className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-accent hover:underline" href={EVIDENCE_URL} download><Download size={13}/>Download evidence JSON</a><span className="text-[11px] text-ink-400">Manifest · environment · stdout · stderr recorded under the run directory</span></div>
      </div>
    </div>
  </article>;
}

function TraceGroup({icon,title,items}:{icon:ReactNode;title:string;items:string[]}){return <div><div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[.1em] text-ink-400">{icon}{title}</div><div className="flex flex-wrap gap-1.5">{items.map((item)=><span key={item} title={item} className="max-w-full truncate rounded-md border border-line bg-[#f7f9fb] px-2 py-1 font-mono text-[9.5px] text-ink-600">{item}</span>)}</div></div>}

function Status({icon,text}:{icon:ReactNode;text:string}){return <span className="inline-flex items-center gap-1.5 rounded-full border border-[#cde2df] bg-[#eff8f6] px-3 py-1.5 text-[11px] font-semibold text-[#176e69]">{icon}{text}</span>}
function ImpactBar({label,value,max,color}:{label:string;value:number;max:number;color:string}){return <div><div className="mb-1.5 flex justify-between text-[12px]"><span className="text-ink-500">{label}</span><span className="data-num font-semibold">{fmt(value)}</span></div><div className="h-2.5 overflow-hidden rounded-full bg-[#e8edf2]"><div className={`h-full rounded-full ${color}`} style={{width:`${Math.max(3,value/max*100)}%`}}/></div></div>}
function Metric({label,value}:{label:string;value:string}){return <div className="rounded-lg bg-[#f5f7fa] p-3"><div className="text-[10px] uppercase tracking-wide text-ink-400">{label}</div><div className="data-num mt-1 text-[13px] font-semibold">{value}</div></div>}
function MetricCard({title,value,note}:{title:string;value:string;note:string}){return <article className="card p-5"><div className="text-[12px] font-semibold text-ink-500">{title}</div><div className="data-num mt-2 font-serif text-[27px] font-semibold text-[#263b59]">{value}</div><p className="mt-2 text-[12px] leading-relaxed text-ink-400">{note}</p></article>}
function Trace({label,value}:{label:string;value:string}){return <div className="grid grid-cols-[78px_1fr] gap-2"><dt>{label}</dt><dd className="truncate font-mono text-[10px] text-ink-700" title={value}>{value}</dd></div>}
function fmt(value:number){return value.toFixed(6)} function signed(value:number){return `${value>=0?'+':''}${value.toFixed(6)}`}
