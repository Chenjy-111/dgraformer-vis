import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Billboard, Html, Line, OrbitControls, QuadraticBezierLine, Ring } from '@react-three/drei';
import { useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import type { GraphEdge } from '@/types/demo';

interface Props {
  variables: string[]; windows: GraphEdge[][]; activeWindow: number; target: number;
  threshold: number; spacing: number; selectedNode: number | null;
  selectedEdge: { source: number; target: number } | null;
  onSelectWindow: (index: number) => void; onSelectNode: (index: number) => void;
  onSelectEdge: (edge: GraphEdge, windowIndex: number) => void;
}
type CameraMode = 'focus' | 'overview';

export function DynamicGraph3D(props: Props) {
  const [cameraMode, setCameraMode] = useState<CameraMode>('focus');
  const current = props.windows[props.activeWindow] ?? [];
  const visible = current.filter((e) => Math.abs(e.weight) >= props.threshold);
  const retained = visible.filter((e) => e.kept);
  const mean = retained.length ? retained.reduce((n, e) => n + Math.abs(e.weight), 0) / retained.length : 0;
  const strongest = [...retained].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))[0];

  return (
    <div className="relative h-[610px] overflow-hidden rounded-xl border border-[#d7dee8] bg-[#f4f7fb] shadow-[inset_0_1px_0_rgba(255,255,255,.9)]">
      <div className="absolute inset-x-0 top-0 z-10 flex items-start justify-between bg-gradient-to-b from-white/95 to-transparent p-4 pb-10">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[.18em] text-[#718096]">Dynamic correlation laboratory</div>
          <div className="mt-1 flex items-baseline gap-2"><span className="text-lg font-semibold text-[#233047]">Window {props.activeWindow + 1}</span><span className="text-[11px] text-[#7b879a]">{retained.length} essential edges · μ {mean.toFixed(3)}</span></div>
        </div>
        <div className="flex rounded-lg border border-[#d6dde7] bg-white/90 p-0.5 shadow-sm backdrop-blur">
          {(['focus', 'overview'] as CameraMode[]).map((mode) => <button key={mode} onClick={() => setCameraMode(mode)} className={`rounded-md px-3 py-1.5 text-[11px] font-medium capitalize transition ${cameraMode === mode ? 'bg-[#263b59] text-white shadow-sm' : 'text-[#66748a] hover:bg-[#edf1f6]'}`}>{mode}</button>)}
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-4 left-4 z-10 w-[210px] rounded-lg border border-white/80 bg-white/88 p-3 shadow-[0_8px_28px_rgba(42,55,78,.12)] backdrop-blur-md">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-[.14em] text-[#758196]">Current graph evidence</div>
        <Metric label="Retained / visible" value={`${retained.length} / ${visible.length}`} />
        <Metric label="Retention rate" value={`${visible.length ? Math.round(retained.length / visible.length * 100) : 0}%`} />
        <Metric label="Strongest relation" value={strongest ? `${props.variables[strongest.source]} → ${props.variables[strongest.target]}` : '—'} accent />
      </div>
      <div className="pointer-events-none absolute bottom-4 right-4 z-10 rounded-lg border border-white/80 bg-white/85 px-3 py-2 text-[10.5px] leading-5 text-[#718096] shadow-sm backdrop-blur">
        <div><i className="mr-2 inline-block h-1.5 w-5 rounded bg-[#16827f]" />essential correlation</div>
        <div><i className="mr-2 inline-block h-px w-5 bg-[#aeb8c6]" />filtered correlation</div>
        <div className="mt-1 border-t border-[#e5e9ef] pt-1">Drag to orbit · wheel to zoom · select graph elements</div>
      </div>

      <Canvas camera={{ position: [0, 4.8, 10.5], fov: 40 }} dpr={[1, 1.75]} gl={{ antialias: true }}>
        <color attach="background" args={['#f4f7fb']} />
        <fog attach="fog" args={['#f4f7fb', 13, 28]} />
        <ambientLight intensity={1.15} />
        <directionalLight position={[4, 7, 8]} intensity={1.5} />
        <pointLight position={[-4, 2, 4]} color="#9dd8d5" intensity={1.4} />
        <CameraRig activeWindow={props.activeWindow} count={props.windows.length} spacing={props.spacing} mode={cameraMode} />
        <GraphLaboratory {...props} />
        <OrbitControls makeDefault enableDamping dampingFactor={0.07} minDistance={6} maxDistance={24} enablePan={false} />
      </Canvas>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return <div className="flex items-start justify-between gap-3 border-t border-[#e8ecf1] py-1.5 first:border-0"><span className="text-[10.5px] text-[#7a8799]">{label}</span><span className={`text-right text-[10.5px] font-semibold ${accent ? 'text-[#167a77]' : 'text-[#344158]'}`}>{value}</span></div>;
}

function CameraRig({ activeWindow, count, spacing, mode }: { activeWindow: number; count: number; spacing: number; mode: CameraMode }) {
  const { camera } = useThree();
  const center = (count - 1) * spacing * .5;
  useFrame((_, dt) => {
    const x = mode === 'focus' ? activeWindow * spacing - center : 0;
    const target = mode === 'focus' ? new THREE.Vector3(x, 3.6, 9.5) : new THREE.Vector3(0, 8.5, Math.max(14, count * spacing * .72));
    camera.position.lerp(target, 1 - Math.exp(-dt * 2.7));
    camera.lookAt(mode === 'focus' ? x : 0, 0, 0);
  });
  return null;
}

function GraphLaboratory(props: Props) {
  const { variables, windows, activeWindow, spacing, target } = props;
  const radius = 2.15;
  const center = (windows.length - 1) * spacing * .5;
  const positions = useMemo(() => variables.map((_, i) => {
    const a = i / variables.length * Math.PI * 2 - Math.PI / 2;
    return new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0);
  }), [variables]);
  return <group rotation={[-.08, 0, 0]}>
    {windows.map((edges, wi) => <WindowGraph key={wi} {...props} edges={edges} windowIndex={wi} active={wi === activeWindow} positionX={wi * spacing - center} positions={positions} />)}
    {positions.map((p, ni) => <Line key={ni} points={windows.map((_, wi) => [wi * spacing - center + p.x, p.y, -.22])} color={ni === target ? '#cf553f' : '#bac4d1'} lineWidth={ni === target ? 1.1 : .45} transparent opacity={ni === target ? .28 : .12} />)}
  </group>;
}

function WindowGraph({ edges, windowIndex, active, positionX, positions, ...props }: Props & { edges: GraphEdge[]; windowIndex: number; active: boolean; positionX: number; positions: THREE.Vector3[] }) {
  const [hoverNode, setHoverNode] = useState<number | null>(null);
  const visible = edges.filter((e) => Math.abs(e.weight) >= props.threshold && (active || e.kept));
  return <group position={[positionX, 0, active ? .25 : -.3]} scale={active ? 1.08 : .78}>
    <mesh onClick={(e) => { e.stopPropagation(); props.onSelectWindow(windowIndex); }}>
      <circleGeometry args={[2.65, 72]} /><meshPhysicalMaterial color={active ? '#f7ffff' : '#ffffff'} transparent opacity={active ? .82 : .28} roughness={.82} transmission={active ? .08 : 0} depthWrite={false} />
    </mesh>
    <Ring args={[2.61, 2.66, 72]} position={[0, 0, .015]}><meshBasicMaterial color={active ? '#16827f' : '#b8c2cf'} transparent opacity={active ? .8 : .25} /></Ring>
    <Billboard position={[0, 2.92, .1]}><Html center distanceFactor={8} style={{ pointerEvents: 'none' }}><div className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] font-semibold tracking-wide shadow-sm ${active ? 'border-[#16827f] bg-[#16827f] text-white' : 'border-[#d5dbe4] bg-white/80 text-[#7b8797]'}`}>WINDOW {windowIndex + 1}</div></Html></Billboard>
    {visible.map((edge, i) => <CorrelationEdge key={`${edge.source}-${edge.target}-${i}`} edge={edge} active={active} selected={active && props.selectedEdge?.source === edge.source && props.selectedEdge?.target === edge.target} dimmed={props.selectedNode != null && edge.source !== props.selectedNode && edge.target !== props.selectedNode} a={positions[edge.source]} b={positions[edge.target]} onClick={() => { props.onSelectWindow(windowIndex); props.onSelectEdge(edge, windowIndex); }} />)}
    {positions.map((p, ni) => <Node key={ni} p={p} name={props.variables[ni]} active={active} target={ni === props.target} selected={ni === props.selectedNode} hovered={ni === hoverNode} onHover={(v) => setHoverNode(v ? ni : null)} onClick={() => { props.onSelectWindow(windowIndex); props.onSelectNode(ni); }} />)}
  </group>;
}

function CorrelationEdge({ edge, active, selected, dimmed, a, b, onClick }: { edge: GraphEdge; active: boolean; selected: boolean; dimmed: boolean; a: THREE.Vector3; b: THREE.Vector3; onClick: () => void }) {
  const particle = useRef<THREE.Mesh>(null);
  const bend = new THREE.Vector3((a.x + b.x) / 2, (a.y + b.y) / 2, .22 + a.distanceTo(b) * .12);
  useFrame(({ clock }) => {
    if (!particle.current || !active || !edge.kept) return;
    const t = (clock.elapsedTime * (.18 + Math.abs(edge.weight) * .25) + edge.source * .13) % 1;
    const p = new THREE.QuadraticBezierCurve3(a, bend, b).getPoint(t); particle.current.position.copy(p);
  });
  const color = selected ? '#cf503d' : edge.kept ? '#16827f' : '#aeb8c6';
  const opacity = dimmed ? .05 : selected ? 1 : active ? edge.kept ? .78 : .16 : .14;
  return <group onClick={(e) => { e.stopPropagation(); onClick(); }}>
    <QuadraticBezierLine start={a} end={b} mid={bend} color={color} lineWidth={selected ? 4.2 : edge.kept ? 1.1 + Math.abs(edge.weight) * 2.5 : .55} dashed={!edge.kept} dashSize={.06} gapSize={.045} transparent opacity={opacity} />
    {active && edge.kept && !dimmed && <mesh ref={particle}><sphereGeometry args={[selected ? .055 : .035, 10, 10]} /><meshBasicMaterial color={selected ? '#ef8a72' : '#63c8c2'} transparent opacity={.9} /></mesh>}
  </group>;
}

function Node({ p, name, active, target, selected, hovered, onHover, onClick }: { p: THREE.Vector3; name: string; active: boolean; target: boolean; selected: boolean; hovered: boolean; onHover: (v: boolean) => void; onClick: () => void }) {
  const ring = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => { if (ring.current) ring.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 2.2) * .08); });
  const color = target ? '#cf503d' : selected ? '#425aa5' : active ? '#354862' : '#8794a6';
  return <group position={p} onPointerOver={(e) => { e.stopPropagation(); onHover(true); }} onPointerOut={() => onHover(false)} onClick={(e) => { e.stopPropagation(); onClick(); }}>
    {(target || selected) && <mesh ref={ring} position={[0, 0, -.01]}><ringGeometry args={[.17, .225, 32]} /><meshBasicMaterial color={color} transparent opacity={.25} side={THREE.DoubleSide} /></mesh>}
    <mesh scale={hovered ? 1.32 : active ? 1.08 : .9}><sphereGeometry args={[target ? .145 : .115, 24, 24]} /><meshStandardMaterial color={color} roughness={.25} metalness={.12} emissive={color} emissiveIntensity={hovered ? .32 : .06} /></mesh>
    {(active || hovered) && <Billboard position={[0, .28, .04]}><Html center distanceFactor={8.5} style={{ pointerEvents: 'none' }}><div className={`whitespace-nowrap rounded border px-1.5 py-0.5 text-[9.5px] shadow-sm ${target ? 'border-[#edc7bf] bg-white/95 font-semibold text-[#b44332]' : 'border-[#dce2ea] bg-white/92 text-[#344158]'}`}>{name}</div></Html></Billboard>}
  </group>;
}
