import { useDemoStore } from '@/store/useDemoStore';
import { ForecastView } from './ForecastView';
import { DynamicGraphView } from './DynamicGraphView';
import { TopKFocusingView } from './TopKFocusingView';
import { MultiScaleAttentionView } from './MultiScaleAttentionView';
import { ErrorDiagnosisView } from './ErrorDiagnosisView';
import { ParameterSensitivityView } from './ParameterSensitivityView';
import { NarrativeReportView } from './NarrativeReportView';

export function VisualizationCanvas() {
  const view = useDemoStore((s) => s.view);
  const loading = useDemoStore((s) => s.loading);
  const sample = useDemoStore((s) => s.sample);
  const immersive3D = useDemoStore((s) => s.view === 'graph' && s.graphLayout === '3d-timeline');

  if (loading && !sample) {
    return <div className="card flex h-[420px] items-center justify-center text-[13px] text-ink-400">Loading artifact…</div>;
  }

  return (
    <div className={immersive3D ? 'absolute inset-0 min-h-[920px]' : 'card min-h-[460px] p-5'}>
      {view === 'forecast' && <ForecastView />}
      {view === 'graph' && <DynamicGraphView />}
      {view === 'topk' && <TopKFocusingView />}
      {view === 'attention' && <MultiScaleAttentionView />}
      {view === 'error' && <ErrorDiagnosisView />}
      {view === 'sensitivity' && <ParameterSensitivityView />}
      {view === 'narrative' && <NarrativeReportView />}
    </div>
  );
}
