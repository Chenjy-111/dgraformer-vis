import { useRef } from 'react';
import { Database, FileJson, LoaderCircle, RotateCcw, ShieldCheck, Upload, X } from 'lucide-react';
import { useAuditSessionStore } from '@/store/useAuditSessionStore';
import { useWorkflowStore } from '@/store/useWorkflowStore';

export function AuditSessionImport() {
  const inputRef = useRef<HTMLInputElement>(null);
  const model = useWorkflowStore(state => state.model);
  const setModel = useWorkflowStore(state => state.setModel);
  const source = useAuditSessionStore(state => state.source);
  const sessionV2 = useAuditSessionStore(state => state.sessionV2);
  const fileName = useAuditSessionStore(state => state.fileName);
  const previousModel = useAuditSessionStore(state => state.previousModel);
  const importState = useAuditSessionStore(state => state.importState);
  const errors = useAuditSessionStore(state => state.errors);
  const importFile = useAuditSessionStore(state => state.importFile);
  const closeSession = useAuditSessionStore(state => state.closeSession);
  const clearError = useAuditSessionStore(state => state.clearError);

  const chooseFile = async (file: File | undefined) => {
    if (!file) return;
    const imported = await importFile(file, model);
    if (imported) {
      setModel(String(imported.model.name));
      setTimeout(() => document.getElementById('discovery-workspace')?.scrollIntoView({ behavior: 'smooth' }), 0);
    }
    if (inputRef.current) inputRef.current.value = '';
  };
  const restoreDemo = () => {
    const restoreModel = previousModel ?? 'DGraFormer';
    closeSession();
    setModel(restoreModel);
  };
  const busy = importState === 'reading' || importState === 'validating';

  return <section id="audit-session-source" className="border-b border-line bg-[#f5f7fa]">
    <div className="mx-auto max-w-[1400px] px-5 py-8">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div><div className="eyebrow">Data source</div><h2 className="mt-1 font-serif text-[27px] font-semibold">Choose a data source</h2></div>
        <div className="rounded-full border border-line bg-white px-3 py-1.5 text-[10px] font-semibold text-ink-600">
          {source === 'imported' ? 'Imported Audit Session' : 'Built-in Demo'}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <article className={`rounded-xl border p-5 ${source === 'built_in' ? 'border-accent/40 bg-white shadow-card' : 'border-line bg-white/60'}`}>
          <div className="flex items-center gap-2 text-[#263b59]"><Database size={17}/><h3 className="text-[15px] font-semibold">Explore Built-in Demo</h3></div>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-500">Explore bundled DGraFormer and MSGNet evidence.</p>
          {source === 'imported' && <button onClick={restoreDemo} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-[#263b59] bg-white px-4 py-2 text-[11px] font-semibold text-[#263b59]"><RotateCcw size={14}/>Return to Built-in Demo</button>}
        </article>
        <article className={`rounded-xl border p-5 ${source === 'imported' ? 'border-[#16827f] bg-[#edf7f6]' : 'border-line bg-white'}`}>
          <div className="flex items-center gap-2 text-[#176e69]"><FileJson size={17}/><h3 className="text-[15px] font-semibold">Import Audit Session</h3></div>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-500">Load a Session v2 JSON generated offline.</p>
          <input ref={inputRef} type="file" accept="application/json,.json" className="hidden" onChange={event => void chooseFile(event.target.files?.[0])}/>
          <button disabled={busy} onClick={() => inputRef.current?.click()} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#263b59] px-4 py-2 text-[11px] font-semibold text-white disabled:opacity-60">
            {busy ? <LoaderCircle size={14} className="animate-spin"/> : <Upload size={14}/>}
            {busy ? (importState === 'reading' ? 'Reading file…' : 'Validating session…') : 'Choose DGraInsight Session'}
          </button>
          <p className="mt-2 text-[9px] text-ink-400">Only valid Session v2 files are accepted.</p>
        </article>
      </div>
      <div className="mt-4 rounded-xl border border-line bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="font-semibold text-[#263b59]">Generate a Session JSON</div><p className="mt-1 text-[10px] leading-relaxed text-ink-500">Run these commands from the repository root, then import the output above.</p></div><a className="text-[10px] font-semibold text-[#176e69] underline" href="./docs/CUSTOM_ADAPTER_GUIDE.md">Custom Adapter Guide</a></div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <GenerationStep number="1" title="Prepare the config"><p>Set the model, checkpoint, dataset and parameters.</p><code>configs/my_custom_quick.json</code></GenerationStep>
          <GenerationStep number="2" title="Validate the adapter"><code>python -m dgraudit validate-adapter --config configs/my_custom_quick.json</code><p>Continue only when V01–V09 pass.</p></GenerationStep>
          <GenerationStep number="3" title="Create the JSON"><code>python -m dgraudit wizard --config configs/my_custom_quick.json --output outputs/my_session_v2.json</code><p>Import <b>outputs/my_session_v2.json</b> above.</p></GenerationStep>
        </div>
      </div>

      {sessionV2 && <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><div className="flex items-center gap-2 text-[11px] font-semibold text-emerald-800"><ShieldCheck size={15}/>Validated imported source</div><p className="mt-1 text-[10px] text-emerald-700">{fileName}</p></div>
          <button onClick={restoreDemo} className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-800"><X size={13}/>Close Imported Session</button>
        </div>
        <dl className="mt-4 grid gap-3 text-[10px] sm:grid-cols-2 lg:grid-cols-5">
          <SourceField label="Version" value="Session v2"/><SourceField label="Model" value={sessionV2.model.name as string}/><SourceField label="Dataset" value={sessionV2.dataset.name as string}/><SourceField label="Adapter" value={sessionV2.model.adapter as string}/><SourceField label="Checkpoint" value={`${String(sessionV2.checkpoint.sha256).slice(0, 16)}…`}/>
        </dl>
      </div>}

      {errors.length > 0 && <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">
        <div className="flex items-start justify-between gap-3"><div><h3 className="text-[13px] font-semibold">Invalid or incompatible DGraInsight Audit Session</h3><p className="mt-1 text-[10px] text-red-700">The active data source was not changed.</p></div><button onClick={clearError} aria-label="Dismiss import errors"><X size={15}/></button></div>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-[10px] leading-relaxed">{errors.slice(0, 8).map((error, index) => <li key={`${index}-${error}`}>{error}</li>)}</ul>
        {errors.length > 8 && <p className="mt-2 text-[9px] text-red-700">{errors.length - 8} additional validation errors were suppressed.</p>}
      </div>}
    </div>
  </section>;
}

function SourceField({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-white/70 p-3"><dt className="uppercase tracking-wider text-emerald-700">{label}</dt><dd className="mt-1 break-all font-mono font-semibold text-emerald-950">{value}</dd></div>;
}

function GenerationStep({ number, title, children }: { number: string; title: string; children: React.ReactNode }) {
  return <article className="rounded-xl border border-line bg-[#fafbfd] p-4"><div className="flex items-center gap-2"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#263b59] text-[10px] font-semibold text-white">{number}</span><h3 className="text-[12px] font-semibold text-[#263b59]">{title}</h3></div><div className="mt-3 space-y-2 text-[10px] leading-relaxed text-ink-500 [&_code]:block [&_code]:overflow-x-auto [&_code]:rounded-lg [&_code]:bg-[#eef2f7] [&_code]:p-2.5 [&_code]:font-mono [&_code]:text-[9px] [&_code]:text-ink-700">{children}</div></article>;
}
