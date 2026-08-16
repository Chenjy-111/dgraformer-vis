import type { MsgnetEdgeImpact } from '@/data/msgnetLoader';

export function EdgeMatrixFigure({matrix,names,source,target}:{matrix:number[][];names:string[];source:number;target:number}){
 const max=Math.max(...matrix.flat(),1e-9);
 return <div className="grid gap-1" style={{gridTemplateColumns:`48px repeat(${names.length},1fr)`}}><span/>{names.map(name=><span key={name} className="text-center text-[8px] text-ink-400">{name}</span>)}{matrix.map((row,s)=><div key={s} className="contents"><span className="flex items-center text-[8px] text-ink-400">{names[s]}</span>{row.map((value,t)=><span key={t} title={`${names[s]} → ${names[t]}: ${value.toFixed(6)}`} className={`aspect-square rounded border ${s===source&&t===target?'border-red-600 ring-2 ring-red-300':'border-white'}`} style={{background:s===t?'#e8edf0':`rgba(22,130,127,${.08+.82*value/max})`}}/>)}</div>)}</div>
}

export function ImpactBars({items,selected}:{items:MsgnetEdgeImpact[];selected:MsgnetEdgeImpact}){
 const values=items.map(item=>item.prediction_delta_abs),max=Math.max(...values,1e-9);
 return <div><svg viewBox="0 0 720 190" className="w-full rounded-lg border border-line bg-white" role="img" aria-label="Prediction response across audited tests">{items.map((item,index)=>{const height=item.prediction_delta_abs/max*125;return <g key={item.sample_index}><rect x={65+index*125} y={150-height} width="50" height={height} rx="3" fill={item===selected?'#d65b52':'#16827f'}/><text x={90+index*125} y="170" textAnchor="middle" fontSize="10" fill="#657286">test {item.sample_index}</text><text x={90+index*125} y={Math.max(14,145-height)} textAnchor="middle" fontSize="9" fill="#34445a">{item.prediction_delta_abs.toFixed(4)}</text></g>})}</svg><p className="mt-2 text-[10px] text-ink-400">Bar height is mean absolute prediction change. Labels use the original ETTh1 artifact sample indices; the selected test is highlighted.</p></div>
}

export function DeltaTrajectory({baseline,changed}:{baseline:number[];changed:number[]}){
 const delta=baseline.map((value,index)=>Math.abs(value-changed[index])),max=Math.max(...delta,1e-12),points=delta.map((value,index)=>`${30+index/95*700},${170-value/max*140}`).join(' ');
 return <div><div className="mb-2 flex items-baseline justify-between"><span className="eyebrow">Absolute intervention difference</span><span className="font-mono text-[10px] text-[#d65b52]">max {max.toFixed(6)}</span></div><svg viewBox="0 0 760 195" className="w-full rounded-lg border border-line bg-white" role="img" aria-label="Absolute difference caused by selected edge removal">{[0,1,2,3,4].map(i=><line key={i} x1="30" x2="730" y1={30+i*35} y2={30+i*35} stroke="#e6eaee"/>)}<polyline points={points} fill="rgba(214,91,82,.12)" stroke="#d65b52" strokeWidth="2.5"/></svg><p className="mt-2 text-[10px] text-ink-400">This panel auto-scales to the selected edge, making small but real checkpoint responses visible.</p></div>
}
