import { Canvas } from '@react-three/fiber';
import { Billboard, Html, Line, OrbitControls } from '@react-three/drei';
import { useMemo, useState } from 'react';
import type { GraphEdge } from '@/types/demo';

interface Props {
  variables: string[];
  windows: GraphEdge[][];
  activeWindow: number;
  target: number;
  threshold: number;
  spacing: number;
  selectedNode: number | null;
  selectedEdge: { source: number; target: number } | null;
  onSelectWindow: (index: number) => void;
  onSelectNode: (index: number) => void;
  onSelectEdge: (edge: GraphEdge, windowIndex: number) => void;
}

export function DynamicGraph3D(props: Props) {
  return (
    <div className="relative h-[520px] overflow-hidden rounded-lg border border-line bg-[#f7f9fc]">
      <div className="pointer-events-none absolute left-3 top-3 z-10 rounded border border-line bg-white/90 px-2.5 py-2 text-[11px] leading-relaxed text-ink-400 shadow-sm backdrop-blur">
        <div><span className="inline-block h-1.5 w-4 rounded bg-[#1C7C7A]" /> retained correlation</div>
        <div><span className="inline-block h-px w-4 bg-[#b8c0cd]" /> filtered correlation</div>
        <div className="mt-1">Drag rotate · wheel zoom · click layers and elements</div>
      </div>
      <Canvas camera={{ position: [0, 7.5, 13], fov: 43 }} dpr={[1, 1.75]}>
        <color attach="background" args={['#f7f9fc']} />
        <ambientLight intensity={1.1} />
        <directionalLight position={[5, 8, 6]} intensity={1.25} />
        <GraphTimeline {...props} />
        <OrbitControls makeDefault enableDamping dampingFactor={0.08} minDistance={7} maxDistance={25} />
      </Canvas>
    </div>
  );
}

function GraphTimeline({ variables, windows, activeWindow, target, threshold, spacing, selectedNode, selectedEdge, onSelectWindow, onSelectNode, onSelectEdge }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const radius = 2.25;
  const positions = useMemo(() => variables.map((_, i) => {
    const a = (i / variables.length) * Math.PI * 2 - Math.PI / 2;
    return [Math.cos(a) * radius, Math.sin(a) * radius] as const;
  }), [variables]);
  const center = ((windows.length - 1) * spacing) / 2;

  return (
    <group rotation={[-0.16, -0.2, 0]} position={[0, 0, 0]}>
      {windows.map((edges, wi) => {
        const z = wi * spacing - center;
        const active = wi === activeWindow;
        const visible = edges.filter((e) => Math.abs(e.weight) >= threshold);
        return (
          <group key={wi} position={[0, 0, z]}>
            <mesh onClick={(e) => { e.stopPropagation(); onSelectWindow(wi); }}>
              <circleGeometry args={[radius + 0.45, 64]} />
              <meshBasicMaterial color={active ? '#e9f4f3' : '#ffffff'} transparent opacity={active ? 0.72 : 0.24} depthWrite={false} />
            </mesh>
            <Line points={Array.from({ length: 65 }, (_, i) => { const a = i / 64 * Math.PI * 2; return [Math.cos(a) * (radius + .45), Math.sin(a) * (radius + .45), .015]; })} color={active ? '#1C7C7A' : '#cbd2dc'} lineWidth={active ? 1.4 : .65} transparent opacity={active ? .7 : .36} />
            <Billboard position={[-radius - .75, radius + .55, .08]}>
              <Html center distanceFactor={8} style={{ pointerEvents: 'none' }}>
                <div className={`whitespace-nowrap rounded px-2 py-1 text-[11px] font-medium ${active ? 'bg-[#1C7C7A] text-white shadow' : 'border border-[#d8dde5] bg-white/90 text-[#657188]'}`}>W{wi + 1}</div>
              </Html>
            </Billboard>
            {visible.map((edge, ei) => {
              const a = positions[edge.source]; const b = positions[edge.target];
              const id = `${wi}-${edge.source}-${edge.target}`;
              const chosen = active && selectedEdge?.source === edge.source && selectedEdge?.target === edge.target;
              const related = selectedNode == null || edge.source === selectedNode || edge.target === selectedNode;
              return <Line key={ei} points={[[a[0], a[1], .08], [b[0], b[1], .08]]} color={chosen ? '#d6453b' : edge.kept ? '#1C7C7A' : '#b8c0cd'} lineWidth={chosen ? 4 : edge.kept ? 1 + Math.abs(edge.weight) * 2.6 : .65} dashed={!edge.kept} dashSize={.08} gapSize={.06} transparent opacity={!related ? .08 : hover === id || chosen ? 1 : edge.kept ? .7 : .25} onPointerOver={(e) => { e.stopPropagation(); setHover(id); }} onPointerOut={() => setHover(null)} onClick={(e) => { e.stopPropagation(); onSelectWindow(wi); onSelectEdge(edge, wi); }} />;
            })}
            {positions.map((p, ni) => {
              const isTarget = ni === target; const selected = ni === selectedNode;
              return (
                <group key={ni} position={[p[0], p[1], .16]} onClick={(e) => { e.stopPropagation(); onSelectWindow(wi); onSelectNode(ni); }} onPointerOver={() => setHover(`n-${wi}-${ni}`)} onPointerOut={() => setHover(null)}>
                  <mesh scale={hover === `n-${wi}-${ni}` || selected ? 1.25 : 1}>
                    <sphereGeometry args={[isTarget ? .15 : .11, 20, 20]} />
                    <meshStandardMaterial color={isTarget ? '#d6453b' : selected ? '#4858a8' : active ? '#52627a' : '#8c98aa'} roughness={.38} metalness={.06} />
                  </mesh>
                  {(active || hover === `n-${wi}-${ni}`) && <Billboard position={[0, .27, 0]}><Html center distanceFactor={9} style={{ pointerEvents: 'none' }}><div className={`whitespace-nowrap text-[10px] ${isTarget ? 'font-semibold text-[#c43d35]' : 'text-[#344056]'}`}>{variables[ni]}</div></Html></Billboard>}
                </group>
              );
            })}
          </group>
        );
      })}
      {positions.map((p, ni) => <Line key={`track-${ni}`} points={windows.map((_, wi) => [p[0], p[1], wi * spacing - center + .02])} color={ni === target ? '#d6453b' : '#d8dde5'} lineWidth={ni === target ? 1 : .45} transparent opacity={ni === target ? .28 : .18} />)}
    </group>
  );
}
