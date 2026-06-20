import { useMemo } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { generateNarrative, reportToMarkdown, download, copyText } from '@/engine/narrativeGenerator';
import { Button } from './ui/Button';
import { Copy, Download, Pin } from 'lucide-react';
import { buildForecastExplanation } from '@/engine/explanationEngine';

export function NarrativeReportView() {
  const s = useDemoStore();
  const sample = s.sample;
  const report = useMemo(
    () => (sample ? generateNarrative(sample, s.windowIdx, s.target, s.depth) : null),
    [sample, s.windowIdx, s.target, s.depth]
  );
  if (!sample || !report) return null;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[15px] font-semibold">{report.title}</h3>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            icon={<Copy className="h-3.5 w-3.5" />}
            onClick={() => copyText(reportToMarkdown(report))}
          >
            Copy
          </Button>
          <Button
            size="sm"
            variant="outline"
            icon={<Download className="h-3.5 w-3.5" />}
            onClick={() => download(`${sample.dataset}_s${sample.sample_id}_h${sample.horizon}_report.md`, reportToMarkdown(report), 'text/markdown')}
          >
            Markdown
          </Button>
          <Button
            size="sm"
            variant="outline"
            icon={<Pin className="h-3.5 w-3.5" />}
            onClick={() =>
              s.pin(buildForecastExplanation({ sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head }))
            }
          >
            Pin
          </Button>
        </div>
      </div>

      <article className="card max-h-[560px] overflow-y-auto p-6">
        {report.sections.map((sec) => (
          <section key={sec.heading} className="mb-4 last:mb-0">
            <h4 className="font-serif text-[15px] font-semibold text-ink-900">{sec.heading}</h4>
            <p className="mt-1 text-[13.5px] leading-relaxed text-ink-700">{sec.body}</p>
          </section>
        ))}
      </article>

      <p className="mt-3 text-[12.5px] text-ink-400">
        Depth follows the Explanation depth control (Brief / Standard / Technical). Change the dataset, window or
        target to regenerate the report for a different case.
      </p>
    </div>
  );
}
