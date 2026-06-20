import { ArrowRight, Compass, Network, Workflow } from 'lucide-react';
import { Button } from './ui/Button';
import { useDemoStore } from '@/store/useDemoStore';

const CHAIN = [
  'Forecast',
  'Window',
  'Dynamic graph',
  'Top-K focusing',
  'Message passing',
  'Multi-scale attention',
  'Error',
  'Report',
];

export function Hero() {
  const startTour = useDemoStore((s) => s.startTour);
  const setView = useDemoStore((s) => s.setView);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  }

  return (
    <section id="top" className="border-b border-line bg-white">
      <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-20">
        <div>
          <div className="eyebrow mb-3">IJCAI-25 · Demo Track · interactive explanation system</div>
          <h1 className="font-serif text-[40px] font-semibold leading-[1.05] tracking-tight md:text-[52px]">
            DGraFormer<span className="text-accent">-Vis</span>
          </h1>
          <p className="mt-3 max-w-xl text-[17px] leading-snug text-ink-700">
            Interactive explanation of dynamic graph learning and multi-scale temporal forecasting.
          </p>
          <p className="mt-5 max-w-xl text-[14.5px] leading-relaxed text-ink-500">
            This demo explains how DGraFormer forecasts multivariate time series by dynamically learning
            inter-variable graphs, focusing on essential correlations, and extracting temporal patterns at
            multiple scales. Every artifact shown is precomputed and loaded statically — no upload, no training,
            no in-browser inference.
          </p>
          <div className="mt-7 flex flex-wrap gap-2.5">
            <Button variant="primary" icon={<ArrowRight size={15} />} onClick={() => { setView('forecast'); scrollTo('workspace'); }}>
              Launch interactive demo
            </Button>
            <Button variant="outline" icon={<Compass size={15} />} onClick={startTour}>Start guided tour</Button>
            <Button variant="outline" icon={<Workflow size={15} />} onClick={() => scrollTo('method')}>View model mechanism</Button>
            <Button variant="outline" icon={<Network size={15} />} onClick={() => scrollTo('cases')}>Explore case studies</Button>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-8 gap-y-2 text-[12.5px] text-ink-500">
            <Stat k="10" v="real-world datasets" />
            <Stat k="11%" v="MSE reduction vs MSGNet" />
            <Stat k="2" v="components: DCGL + MTT" />
            <Stat k="3" v="temporal scales" />
          </div>
        </div>

        {/* signature: the explanation chain */}
        <div className="card flex flex-col justify-center p-6">
          <div className="eyebrow mb-4">The explanation chain</div>
          <ol className="relative ml-3 border-l border-dashed border-line">
            {CHAIN.map((step, i) => (
              <li key={step} className="relative mb-3 pl-5 last:mb-0">
                <span className="absolute -left-[7px] top-1 h-3 w-3 rounded-full border-2 border-white bg-accent" />
                <div className="flex items-center gap-2">
                  <span className="data-num text-[11px] text-ink-400">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-[13.5px] font-medium text-ink-900">{step}</span>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-4 text-[12px] leading-relaxed text-ink-400">
            Each link is a panel in the workspace. The demo threads them into one path from a single prediction
            back to the mechanism that produced it.
          </p>
        </div>
      </div>
    </section>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-serif text-[20px] font-semibold text-accent">{k}</span>
      <span>{v}</span>
    </div>
  );
}
