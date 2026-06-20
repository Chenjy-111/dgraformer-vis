import { Section } from './layout/Section';

const BIBTEX = `@inproceedings{yan2025dgraformer,
  title     = {DGraFormer: Dynamic Graph Learning Guided Multi-Scale
               Transformer for Multivariate Time Series Forecasting},
  author    = {Yan, Han and Chen, Dongliang and Jiang, Guiyuan and
               Wang, Bin and Cao, Lei and Dong, Junyu and Yu, Yanwei},
  booktitle = {Proceedings of the Thirty-Fourth International Joint
               Conference on Artificial Intelligence (IJCAI-25)},
  pages     = {3516--3524},
  year      = {2025}
}`;

export function CitationSection() {
  return (
    <Section id="cite" eyebrow="Reference" title="Paper and citation">
      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <div className="card p-5">
          <p className="text-[14px] leading-relaxed text-ink-700">
            DGraFormer: Dynamic Graph Learning Guided Multi-Scale Transformer for Multivariate Time Series
            Forecasting.
          </p>
          <p className="mt-2 text-[13px] text-ink-500">
            Han Yan, Dongliang Chen, Guiyuan Jiang, Bin Wang, Lei Cao, Junyu Dong, Yanwei Yu. IJCAI-25,
            pp. 3516–3524.
          </p>
          <p className="mt-3 text-[13px] text-ink-500">
            Official code:{' '}
            <a
              className="text-accent underline-offset-2 hover:underline"
              href="https://github.com/yh-Hanniel/DGraFormer"
              target="_blank"
              rel="noreferrer"
            >
              github.com/yh-Hanniel/DGraFormer
            </a>
          </p>
          <p className="mt-3 text-[12px] leading-relaxed text-ink-400">
            DGraFormer-Vis is an independent, unofficial explanation/visualization demo built around the published
            method. It is not affiliated with the original authors.
          </p>
        </div>
        <div className="card p-5">
          <div className="eyebrow mb-2">BibTeX</div>
          <pre className="overflow-x-auto rounded-md bg-paper p-3 font-mono text-[11.5px] leading-relaxed text-ink-700">
            {BIBTEX}
          </pre>
        </div>
      </div>
    </Section>
  );
}
