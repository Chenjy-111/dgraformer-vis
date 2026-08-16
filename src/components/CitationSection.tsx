import { Section } from './layout/Section';

const DGRAFORMER_BIBTEX = `@inproceedings{yan2025dgraformer,
  title     = {DGraFormer: Dynamic Graph Learning Guided Multi-Scale
               Transformer for Multivariate Time Series Forecasting},
  author    = {Yan, Han and Chen, Dongliang and Jiang, Guiyuan and
               Wang, Bin and Cao, Lei and Dong, Junyu and Yu, Yanwei},
  booktitle = {Proceedings of the Thirty-Fourth International Joint
               Conference on Artificial Intelligence (IJCAI-25)},
  pages     = {3516--3524},
  year      = {2025}
}`;

const MSGNET_BIBTEX = `@inproceedings{cai2024msgnet,
  title     = {{MSGNet}: Learning Multi-Scale Inter-Series Correlations
               for Multivariate Time Series Forecasting},
  author    = {Cai, Wanlin and Liang, Yuxuan and Liu, Xianggen and
               Feng, Jianshuai and Wu, Yuankai},
  booktitle = {Proceedings of the AAAI Conference on Artificial Intelligence},
  volume    = {38},
  number    = {10},
  pages     = {11141--11149},
  year      = {2024},
  doi       = {10.1609/aaai.v38i10.28991}
}`;

export function CitationSection() {
  return <Section id="cite" eyebrow="Citation & code" title="Supported forecasting model references" intro="DGraInsight provides a shared evidence-validation workflow over two independently published forecasting architectures. The model contributions remain credited to their original authors.">
    <div className="grid gap-5 lg:grid-cols-2">
      <PaperCard model="DGraFormer" context="Window-level learned graph adapter" title="DGraFormer: Dynamic Graph Learning Guided Multi-Scale Transformer for Multivariate Time Series Forecasting" authors="Han Yan, Dongliang Chen, Guiyuan Jiang, Bin Wang, Lei Cao, Junyu Dong, and Yanwei Yu" venue="IJCAI 2025 · pp. 3516–3524" code="https://github.com/yh-Hanniel/DGraFormer" bibtex={DGRAFORMER_BIBTEX}/>
      <PaperCard model="MSGNet" context="Scale-level learned graph adapter" title="MSGNet: Learning Multi-Scale Inter-Series Correlations for Multivariate Time Series Forecasting" authors="Wanlin Cai, Yuxuan Liang, Xianggen Liu, Jianshuai Feng, and Yuankai Wu" venue="AAAI 2024 · Vol. 38(10) · pp. 11141–11149" paper="https://doi.org/10.1609/aaai.v38i10.28991" code="https://github.com/YoZhibo/MSGNet" bibtex={MSGNET_BIBTEX}/>
    </div>
    <div className="mt-5 rounded-xl border border-line bg-white p-5 text-[11px] leading-relaxed text-ink-500"><b className="text-ink-800">System attribution.</b> DGraInsight is an independent evidence-validation system built around checkpoint artifacts from these model adapters. It does not claim the graph-learning, forecasting, or temporal-scale mechanisms introduced by either source paper. A dedicated DGraInsight citation should be added here only after the system paper is publicly available.</div>
  </Section>;
}

function PaperCard({model,context,title,authors,venue,paper,code,bibtex}:{model:string;context:string;title:string;authors:string;venue:string;paper?:string;code:string;bibtex:string}) {
  return <article className="card overflow-hidden"><header className="border-b border-line bg-[#fafbfd] p-5"><div className="eyebrow">{model} · supported adapter</div><h3 className="mt-2 text-[19px] font-semibold leading-snug">{title}</h3><p className="mt-3 text-[12px] leading-relaxed text-ink-500">{authors}</p><p className="mt-2 text-[11px] font-semibold text-ink-700">{venue}</p><p className="mt-1 text-[10px] text-ink-400">DGraInsight context: {context}</p><div className="mt-4 flex flex-wrap gap-2">{paper&&<a className="rounded-lg bg-[#263b59] px-3 py-2 text-[10px] font-semibold text-white" href={paper} target="_blank" rel="noreferrer">Official paper</a>}<a className="rounded-lg border border-[#263b59] bg-white px-3 py-2 text-[10px] font-semibold text-[#263b59]" href={code} target="_blank" rel="noreferrer">Official code</a></div></header><div className="p-5"><div className="eyebrow mb-2">BibTeX</div><pre className="overflow-x-auto rounded-md bg-paper p-3 font-mono text-[10px] leading-relaxed text-ink-700">{bibtex}</pre></div></article>;
}
