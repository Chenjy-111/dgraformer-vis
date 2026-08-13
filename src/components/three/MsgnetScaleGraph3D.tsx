import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Billboard, Html, Line, OrbitControls, QuadraticBezierLine, Ring } from '@react-three/drei';
import { useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import type { GraphEdge } from '@/types/demo';
import type { MsgnetContext } from '@/data/msgnetLoader';

interface Props {
  variables: string[];
  contexts: MsgnetContext[];
  graphs: GraphEdge[][];
  activeScale: number;
  selectedEdge: { source: number; target: number } | null;
  onSelectScale: (scale: number) => void;
  onSelectEdge: (edge: GraphEdge, scale: number) => void;
}

export function MsgnetScaleGraph3D(props: Props) {
  const [overview, setOverview] = useState(false);
  const current = props.graphs[props.activeScale] ?? [];
  const strongest = current[0];
  return <div className="relative h-[720px] w-full overflow-hidden rounded-lg bg-[#eef3f8]">
    <div className="absolute left-5 right-5 top-5 z-10 flex items-start justify-between rounded-xl border border-white/70 bg-white/75 p-4 shadow-sm backdrop-blur-md">
      <div><div className="text-[10px] font-semibold uppercase tracking-[.18em] text-[#718096]">Multi-scale graph laboratory</div><div className="mt-1 flex items-baseline gap-2"><span className="text-lg font-semibold text-[#233047]">Scale {props.activeScale + 1}</span><span className="text-[11px] text-[#7b879a]">period {props.contexts[props.activeScale].period} · {current.length} real relations</span></div></div>
      <div className="flex rounded-lg border border-[#d6dde7] bg-white/90 p-0.5 shadow-sm">{([['focus',false],['overview',true]] as const).map(([label,value])=><button key={label} onClick={()=>setOverview(value)} className={`rounded-md px-3 py-1.5 text-[11px] font-medium capitalize ${overview===value?'bg-[#263b59] text-white':'text-[#66748a]'}`}>{label}</button>)}</div>
    </div>
    <div className="pointer-events-none absolute bottom-5 left-5 z-10 rounded-lg border border-white/80 bg-white/88 p-3 shadow-md backdrop-blur"><div className="text-[9px] font-semibold uppercase tracking-wider text-[#758196]">Current graph evidence</div><div className="mt-2 text-[10px] text-[#6f7d90]">Strongest relation</div><div className="text-[11px] font-semibold text-[#167a77]">{strongest?`${props.variables[strongest.source]} → ${props.variables[strongest.target]} · ${strongest.weight.toFixed(3)}`:'—'}</div></div>
    <div className="pointer-events-none absolute bottom-5 right-5 z-10 rounded-lg border border-white/80 bg-white/88 px-3 py-2 text-[10px] text-[#718096] shadow-md backdrop-blur">Drag to orbit · wheel to zoom · click edges and scale layers</div>
    <Canvas camera={{position:[0,4.8,10.5],fov:40}} dpr={[1,1.75]} gl={{antialias:true}}>
      <color attach="background" args={['#f4f7fb']}/><fog attach="fog" args={['#f4f7fb',13,28]}/><ambientLight intensity={1.15}/><directionalLight position={[4,7,8]} intensity={1.5}/><pointLight position={[-4,2,4]} color="#9dd8d5" intensity={1.4}/>
      <CameraRig active={props.activeScale} count={props.graphs.length} spacing={4.8} overview={overview}/><ScaleLaboratory {...props}/><OrbitControls makeDefault enableDamping dampingFactor={.07} minDistance={6} maxDistance={24} enablePan={false}/>
    </Canvas>
  </div>;
}

function CameraRig({active,count,spacing,overview}:{active:number;count:number;spacing:number;overview:boolean}){const {camera}=useThree(),center=(count-1)*spacing*.5;useFrame((_,dt)=>{const x=active*spacing-center,target=overview?new THREE.Vector3(0,8.5,14):new THREE.Vector3(x,3.6,9.5);camera.position.lerp(target,1-Math.exp(-dt*2.7));camera.lookAt(overview?0:x,0,0)});return null}
function ScaleLaboratory(props:Props){const radius=2.15,spacing=4.8,center=(props.graphs.length-1)*spacing*.5,positions=useMemo(()=>props.variables.map((_,i)=>{const a=i/props.variables.length*Math.PI*2-Math.PI/2;return new THREE.Vector3(Math.cos(a)*radius,Math.sin(a)*radius,0)}),[props.variables]);return <group rotation={[-.08,0,0]}>{props.graphs.map((edges,i)=><ScaleLayer key={i} {...props} edges={edges} index={i} active={i===props.activeScale} x={i*spacing-center} positions={positions}/>)}{positions.map((p,i)=><Line key={i} points={props.graphs.map((_,s)=>[s*spacing-center+p.x,p.y,-.22])} color="#bac4d1" lineWidth={.45} transparent opacity={.13}/>)}</group>}
function ScaleLayer({edges,index,active,x,positions,...props}:Props&{edges:GraphEdge[];index:number;active:boolean;x:number;positions:THREE.Vector3[]}){return <group position={[x,0,active?.35:-.4]} rotation={[-.07,-.47,-.026]} scale={active?1.04:.76}>
  <mesh onClick={e=>{e.stopPropagation();props.onSelectScale(index)}}><circleGeometry args={[2.65,72]}/><meshPhysicalMaterial color={active?'#f7ffff':'#fff'} transparent opacity={active?.9:.28} roughness={.82} depthWrite={false}/></mesh><Ring args={[2.61,2.66,72]} position={[0,0,.015]}><meshBasicMaterial color={active?'#16827f':'#b8c2cf'} transparent opacity={active?.9:.25}/></Ring>
  <Billboard position={[0,2.92,.1]}><Html center distanceFactor={8} style={{pointerEvents:'none'}}><div className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] font-semibold shadow-sm ${active?'border-[#16827f] bg-[#16827f] text-white':'border-[#d5dbe4] bg-white/80 text-[#7b8797]'}`}>SCALE {index+1} · P{props.contexts[index].period}</div></Html></Billboard>
  {edges.map((edge,i)=><Edge3D key={`${edge.source}-${edge.target}-${i}`} edge={edge} variables={props.variables} active={active} selected={active&&props.selectedEdge?.source===edge.source&&props.selectedEdge.target===edge.target} a={positions[edge.source]} b={positions[edge.target]} onClick={()=>{props.onSelectScale(index);props.onSelectEdge(edge,index)}}/>)}
  {positions.map((p,i)=><Node3D key={i} p={p} name={props.variables[i]} active={active}/>)}</group>}
function Edge3D({edge,variables,active,selected,a,b,onClick}:{edge:GraphEdge;variables:string[];active:boolean;selected:boolean;a:THREE.Vector3;b:THREE.Vector3;onClick:()=>void}){const particle=useRef<THREE.Mesh>(null),[hover,setHover]=useState(false),bend=new THREE.Vector3((a.x+b.x)/2,(a.y+b.y)/2,.22+a.distanceTo(b)*.12);useFrame(({clock})=>{if(!particle.current||!active)return;particle.current.position.copy(new THREE.QuadraticBezierCurve3(a,bend,b).getPoint((clock.elapsedTime*(.18+edge.weight*.25)+edge.source*.13)%1))});return <group onClick={e=>{e.stopPropagation();onClick()}} onPointerOver={e=>{e.stopPropagation();setHover(true);document.body.style.cursor='pointer'}} onPointerOut={()=>{setHover(false);document.body.style.cursor='default'}}><QuadraticBezierLine start={a} end={b} mid={bend} color={selected?'#cf503d':'#16827f'} lineWidth={hover||selected?4:1.1+edge.weight*2.8} transparent opacity={active?.88:.14}/>{active&&<mesh ref={particle}><sphereGeometry args={[selected?.055:.035,10,10]}/><meshBasicMaterial color={selected?'#ef8a72':'#63c8c2'}/></mesh>}{hover&&<Billboard position={bend}><Html center distanceFactor={8} style={{pointerEvents:'none'}}><div className="min-w-[145px] rounded-lg border border-[#cfd7e2] bg-white/95 p-2.5 text-[10px] shadow-xl"><b>{variables[edge.source]} → {variables[edge.target]}</b><div className="mt-1 flex justify-between"><span>Weight</span><b className="font-mono">{edge.weight.toFixed(4)}</b></div><div className="flex justify-between"><span>Rank</span><b>#{edge.rank}</b></div></div></Html></Billboard>}</group>}
function Node3D({p,name,active}:{p:THREE.Vector3;name:string;active:boolean}){const [hover,setHover]=useState(false);return <group position={p} onPointerOver={e=>{e.stopPropagation();setHover(true)}} onPointerOut={()=>setHover(false)}><mesh scale={hover?1.32:active?1.08:.9}><sphereGeometry args={[.115,24,24]}/><meshStandardMaterial color={active?'#354862':'#8794a6'} roughness={.25} metalness={.12}/></mesh>{(active||hover)&&<Billboard position={[0,.28,.04]}><Html center distanceFactor={8.5} style={{pointerEvents:'none'}}><div className="whitespace-nowrap rounded border border-[#dce2ea] bg-white/95 px-1.5 py-.5 text-[9.5px] shadow-sm">{name}</div></Html></Billboard>}</group>}
