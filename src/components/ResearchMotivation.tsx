import { Section } from './layout/Section';
import { AcademicCard } from './layout/AcademicCard';

const PROBLEMS = [
  {
    title: 'Correlations are left implicit',
    body:
      'Many Transformer forecasters treat each variable as an independent channel and never model inter-variable ' +
      'relationships explicitly. Useful structure — which variables move together — is left for attention to ' +
      'rediscover indirectly, if at all.',
  },
  {
    title: 'Static graphs miss dynamics',
    body:
      'Graph-based methods represent variables as nodes and correlations as edges, but most use a single static ' +
      'graph for the whole sequence. Real relationships drift across time windows with periodicity and external ' +
      'factors, so one fixed graph cannot capture them.',
  },
  {
    title: 'Spurious edges propagate noise',
    body:
      'Real datasets contain temporary, spurious correlations. If every edge is used for message passing, noise ' +
      'is propagated alongside signal, diluting the essential relationships the model should rely on.',
  },
];

export function ResearchMotivation() {
  return (
    <Section
      id="motivation"
      eyebrow="Research motivation"
      title="Three gaps DGraFormer addresses"
      intro="Multivariate forecasting depends on relationships between variables that are neither static nor noise-free. DGraFormer targets three specific shortcomings of prior work."
    >
      <div className="grid gap-4 md:grid-cols-3">
        {PROBLEMS.map((p, i) => (
          <AcademicCard key={p.title} index={`0${i + 1}`} title={p.title}>
            <p className="text-[14px] leading-relaxed text-ink-500">{p.body}</p>
          </AcademicCard>
        ))}
      </div>
      <p className="mt-6 max-w-3xl text-[14px] leading-relaxed text-ink-500">
        The model's answer is to learn a separate correlation graph per time window, keep only the essential edges
        via Top-K focusing, and read temporal structure at multiple patch scales. The rest of this page lets you
        inspect each of those mechanisms on precomputed examples.
      </p>
    </Section>
  );
}
