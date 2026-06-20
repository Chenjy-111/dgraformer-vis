import type { DatasetId, Horizon, SampleData } from '@/types/demo';

const cache = new Map<string, SampleData>();

function key(d: DatasetId, s: number, h: Horizon) {
  return `${d}_${String(s).padStart(3, '0')}_h${h}`;
}

/**
 * Loads a precomputed sample artifact from public/data/samples/.
 * Each JSON file must conform to the SampleData schema and be exported
 * via scripts/export_demo_data.py from real DGraFormer inference runs.
 */
export async function loadSample(dataset: DatasetId, sampleId: number, horizon: Horizon): Promise<SampleData> {
  const k = key(dataset, sampleId, horizon);
  const cached = cache.get(k);
  if (cached) return cached;

  const base = import.meta.env.BASE_URL ?? '/';
  const res = await fetch(`${base}data/samples/${k}.json`);
  if (!res.ok) {
    throw new Error(
      `Sample data not found: ${k}.json. Run scripts/export_demo_data.py to export real DGraFormer inference artifacts.`
    );
  }
  const json = (await res.json()) as SampleData;
  cache.set(k, json);
  return json;
}
