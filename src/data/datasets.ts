import type { DatasetId, DatasetMeta } from '@/types/demo';

export const DATASETS: Record<DatasetId, DatasetMeta> = {
  ETTh1: { id: 'ETTh1', variables: ['HUFL', 'HULL', 'MUFL', 'MULL', 'LUFL', 'LULL', 'OT'], pointsPerDay: 24, venue: 'ETT hourly' },
  ETTh2: { id: 'ETTh2', variables: ['HUFL', 'HULL', 'MUFL', 'MULL', 'LUFL', 'LULL', 'OT'], pointsPerDay: 24, venue: 'ETT hourly' },
  ETTm1: { id: 'ETTm1', variables: ['HUFL', 'HULL', 'MUFL', 'MULL', 'LUFL', 'LULL', 'OT'], pointsPerDay: 96, venue: 'ETT 15-min' },
  ETTm2: { id: 'ETTm2', variables: ['HUFL', 'HULL', 'MUFL', 'MULL', 'LUFL', 'LULL', 'OT'], pointsPerDay: 96, venue: 'ETT 15-min' },
  Weather: { id: 'Weather', variables: ['p', 'T', 'Tpot', 'Tdew', 'rh', 'VPmax', 'VPact', 'VPdef', 'sh', 'H2OC', 'rho', 'wv', 'max. wv', 'wd', 'rain', 'raining', 'SWDR', 'PAR', 'max. PAR', 'Tlog', 'OT'], pointsPerDay: 144, venue: 'Weather 10-min' },
  Electricity: { id: 'Electricity', variables: ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8', 'OT'], pointsPerDay: 24, venue: 'Electricity hourly' },
  Solar: { id: 'Solar', variables: ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'OT'], pointsPerDay: 144, venue: 'Solar 10-min' },
  Traffic: { id: 'Traffic', variables: ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'OT'], pointsPerDay: 24, venue: 'Traffic hourly' },
  Flight: { id: 'Flight', variables: ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'OT'], pointsPerDay: 24, venue: 'Flight hourly' },
  AirQualityUCI: { id: 'AirQualityUCI', variables: ['CO', 'NMHC', 'C6H6', 'NOx', 'NO2', 'O3', 'T', 'RH', 'OT'], pointsPerDay: 24, venue: 'Air Quality hourly' },
};

export const DATASET_IDS = Object.keys(DATASETS) as DatasetId[];
export const SAMPLE_DATASET_IDS: DatasetId[] = ['ETTh1', 'ETTh2', 'ETTm1', 'ETTm2', 'Weather'];

export const LOOKBACK = 96; // T
export const PATCH_LEN = 8; // p
export const SAMPLES_PER_CASE = 5;
