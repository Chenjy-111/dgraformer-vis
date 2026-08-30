import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const ROOT = path.resolve("artifacts/msgnet_cross_test_v1");
const CASE_PATH = path.join(ROOT, "case_evidence.csv");
const RELATION_PATHS = {
  single_scale: path.join(ROOT, "relation_evidence_single_scale.csv"),
  all_scales: path.join(ROOT, "relation_evidence_all_scale.csv"),
};
const REPORT_PATH = path.join(ROOT, "MSGNET_STATISTICAL_FREEZE_AUDIT.md");
const CSV_PATH = path.join(ROOT, "msgnet_supported_sensitivity.csv");

const TEST_IDS = [0, 214, 428, 642, 857, 1071, 1285, 1499, 1713, 1927, 2142, 2356, 2570, 2784];
const SUBSET_A = TEST_IDS.filter((_, i) => i % 2 === 0);
const SUBSET_B = TEST_IDS.filter((_, i) => i % 2 === 1);
const RAW_SPAN_HOURS = 192;
const ALPHA = 0.05;
const EXPECTED_FAMILY_SIZES = { single_scale: 126, all_scales: 42 };

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ',') {
      row.push(field);
      field = "";
    } else if (ch === '\n') {
      row.push(field.endsWith('\r') ? field.slice(0, -1) : field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field.length || row.length) {
    row.push(field.endsWith('\r') ? field.slice(0, -1) : field);
    rows.push(row);
  }
  const [header, ...body] = rows;
  if (!header?.length) throw new Error("CSV has no header");
  return body.filter(r => r.some(v => v !== "")).map((r, idx) => {
    if (r.length !== header.length) throw new Error(`CSV row ${idx + 2} has ${r.length} fields; expected ${header.length}`);
    return Object.fromEntries(header.map((h, j) => [h, r[j]]));
  });
}

function csvCell(value) {
  if (value === null || value === undefined) return "";
  const s = typeof value === "number" ? numberText(value) : String(value);
  return /[",\r\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

function toCsv(headers, rows) {
  return [headers.join(','), ...rows.map(row => headers.map(h => csvCell(row[h])).join(','))].join('\r\n') + '\r\n';
}

function numberText(value) {
  if (!Number.isFinite(value)) throw new Error(`Non-finite output value: ${value}`);
  if (Object.is(value, -0)) return "0";
  return value.toPrecision(16).replace(/(?:\.0+|(?:(\.\d*?[1-9])0+))(?=e|$)/, '$1');
}

function asNumber(value, label) {
  const n = Number(value);
  if (!Number.isFinite(n)) throw new Error(`Invalid numeric value for ${label}: ${value}`);
  return n;
}

function mean(values) {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function choose(n, k) {
  if (k < 0 || k > n) return 0;
  k = Math.min(k, n - k);
  let result = 1;
  for (let i = 1; i <= k; i += 1) result = result * (n - k + i) / i;
  return result;
}

function exactSignTest(values) {
  const positive = values.filter(v => v > 0).length;
  const negative = values.filter(v => v < 0).length;
  const zero = values.length - positive - negative;
  const n = positive + negative;
  if (n === 0) return { p: 1, positive, negative, zero, nEffective: 0 };
  let tail = 0;
  for (let k = positive; k <= n; k += 1) tail += choose(n, k);
  return { p: tail / (2 ** n), positive, negative, zero, nEffective: n };
}

function exactSignFlip(values) {
  const magnitudes = values.map(Math.abs);
  const observed = values.reduce((a, b) => a + b, 0);
  const total = 2 ** values.length;
  const tolerance = Math.max(1, Math.abs(observed), ...magnitudes) * 1e-14;
  let atLeastObserved = 0;
  for (let mask = 0; mask < total; mask += 1) {
    let sum = 0;
    for (let i = 0; i < magnitudes.length; i += 1) {
      sum += ((mask >>> i) & 1 ? 1 : -1) * magnitudes[i];
    }
    if (sum >= observed - tolerance) atLeastObserved += 1;
  }
  return atLeastObserved / total;
}

function adjustedQ(entries, method = "BH") {
  const m = entries.length;
  const harmonic = Array.from({ length: m }, (_, i) => 1 / (i + 1)).reduce((a, b) => a + b, 0);
  const factor = method === "BY" ? harmonic : 1;
  const sorted = entries.map((e, i) => ({ i, p: e.p })).sort((a, b) => a.p - b.p || a.i - b.i);
  const out = Array(m);
  let running = 1;
  for (let rankIndex = m - 1; rankIndex >= 0; rankIndex -= 1) {
    const rank = rankIndex + 1;
    running = Math.min(running, sorted[rankIndex].p * m * factor / rank, 1);
    out[sorted[rankIndex].i] = running;
  }
  return out;
}

function summarize(values) {
  const signs = exactSignTest(values);
  const looMeans = values.map((_, omit) => mean(values.filter((__, i) => i !== omit)));
  return {
    n: values.length,
    mean: mean(values),
    median: median(values),
    positive: signs.positive,
    negative: signs.negative,
    zero: signs.zero,
    signflipP: exactSignFlip(values),
    signTestP: signs.p,
    signTestNEffective: signs.nEffective,
    looMin: Math.min(...looMeans),
  };
}

function near(a, b, tolerance = 2e-12) {
  return Math.abs(a - b) <= tolerance * Math.max(1, Math.abs(a), Math.abs(b));
}

function relationLabel(row) {
  return row.hypothesis_id;
}

// Uniform audit-only classification. This function intentionally receives no edge names or IDs.
function auditClassification(metrics) {
  if (!metrics.bySupported) return "DEPENDENCE-SENSITIVE";
  const directionStable = metrics.subsetAMean > 0 && metrics.subsetBMean > 0 && metrics.subsetAMedian > 0 && metrics.subsetBMedian > 0;
  const resamplingStable = metrics.looMin > 0 && metrics.bootstrapLow > 0;
  if (metrics.signTestSupported && directionStable && resamplingStable) return "STABLE UNDER SENSITIVITY";
  return "MIXED SENSITIVITY";
}

function intervalDiagnostics(ids) {
  const startGaps = ids.slice(1).map((id, i) => id - ids[i]);
  const unusedGaps = startGaps.map(gap => gap - RAW_SPAN_HOURS);
  const overlapCount = startGaps.filter(gap => gap < RAW_SPAN_HOURS).length;
  return {
    rawSpan: RAW_SPAN_HOURS,
    startGaps,
    minStartGap: Math.min(...startGaps),
    unusedGaps,
    minUnusedGap: Math.min(...unusedGaps),
    overlapCount,
  };
}

function formatP(value) {
  if (value === 0) return "0";
  if (value < 0.0001) return value.toExponential(6);
  return value.toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
}

function formatD(value) {
  return value.toPrecision(8);
}

function countIf(rows, predicate) {
  return rows.reduce((n, row) => n + (predicate(row) ? 1 : 0), 0);
}

const [caseText, singleText, allText] = await Promise.all([
  fs.readFile(CASE_PATH, "utf8"),
  fs.readFile(RELATION_PATHS.single_scale, "utf8"),
  fs.readFile(RELATION_PATHS.all_scales, "utf8"),
]);
const cases = parseCsv(caseText);
const relationRows = {
  single_scale: parseCsv(singleText),
  all_scales: parseCsv(allText),
};

if (cases.length !== 2352) throw new Error(`Expected 2352 case rows, found ${cases.length}`);
for (const [family, expected] of Object.entries(EXPECTED_FAMILY_SIZES)) {
  if (relationRows[family].length !== expected) throw new Error(`${family}: expected ${expected} relations, found ${relationRows[family].length}`);
}
const observedTestIds = [...new Set(cases.map(r => asNumber(r.test_id, "test_id")))].sort((a, b) => a - b);
if (JSON.stringify(observedTestIds) !== JSON.stringify(TEST_IDS)) throw new Error(`Frozen test IDs mismatch: ${JSON.stringify(observedTestIds)}`);

const caseGroups = new Map();
for (const row of cases) {
  if (!(row.scope in EXPECTED_FAMILY_SIZES)) throw new Error(`Unexpected scope ${row.scope}`);
  const key = `${row.scope}\u0000${row.hypothesis_id}`;
  if (!caseGroups.has(key)) caseGroups.set(key, []);
  caseGroups.get(key).push({ testId: asNumber(row.test_id, "test_id"), D: asNumber(row.D, "D") });
}
for (const rows of caseGroups.values()) rows.sort((a, b) => a.testId - b.testId);

const familyResults = {};
const validation = { maxMeanDiff: 0, maxMedianDiff: 0, maxSignflipPDiff: 0, maxPrimaryBhQDiff: 0 };
for (const family of Object.keys(EXPECTED_FAMILY_SIZES)) {
  const results = relationRows[family].map(source => {
    const key = `${family}\u0000${source.hypothesis_id}`;
    const group = caseGroups.get(key);
    if (!group || group.length !== 14) throw new Error(`${source.hypothesis_id}: expected 14 case rows`);
    if (JSON.stringify(group.map(r => r.testId)) !== JSON.stringify(TEST_IDS)) throw new Error(`${source.hypothesis_id}: test IDs differ from frozen list`);
    const allValues = group.map(r => r.D);
    const aValues = group.filter(r => SUBSET_A.includes(r.testId)).map(r => r.D);
    const bValues = group.filter(r => SUBSET_B.includes(r.testId)).map(r => r.D);
    const primary = summarize(allValues);
    const a = summarize(aValues);
    const b = summarize(bValues);
    const sourceMean = asNumber(source.mean_D, "mean_D");
    const sourceMedian = asNumber(source.median_D, "median_D");
    const sourceP = asNumber(source.raw_p_exact_signflip, "raw_p_exact_signflip");
    validation.maxMeanDiff = Math.max(validation.maxMeanDiff, Math.abs(primary.mean - sourceMean));
    validation.maxMedianDiff = Math.max(validation.maxMedianDiff, Math.abs(primary.median - sourceMedian));
    validation.maxSignflipPDiff = Math.max(validation.maxSignflipPDiff, Math.abs(primary.signflipP - sourceP));
    if (!near(primary.mean, sourceMean) || !near(primary.median, sourceMedian) || !near(primary.signflipP, sourceP)) {
      throw new Error(`${source.hypothesis_id}: recomputed primary metrics do not match relation evidence`);
    }
    if (primary.positive !== asNumber(source.positive_count, "positive_count") || primary.negative !== asNumber(source.negative_count, "negative_count") || primary.zero !== asNumber(source.zero_count, "zero_count")) {
      throw new Error(`${source.hypothesis_id}: recomputed sign counts do not match relation evidence`);
    }
    return { family, source, primary, a, b };
  });

  const primaryBh = adjustedQ(results.map(r => ({ p: r.primary.signflipP })), "BH");
  const primaryBy = adjustedQ(results.map(r => ({ p: r.primary.signflipP })), "BY");
  const signBh = adjustedQ(results.map(r => ({ p: r.primary.signTestP })), "BH");
  const subsetABh = adjustedQ(results.map(r => ({ p: r.a.signflipP })), "BH");
  const subsetBBh = adjustedQ(results.map(r => ({ p: r.b.signflipP })), "BH");
  const subsetASignBh = adjustedQ(results.map(r => ({ p: r.a.signTestP })), "BH");
  const subsetBSignBh = adjustedQ(results.map(r => ({ p: r.b.signTestP })), "BH");
  results.forEach((r, i) => {
    r.primaryBhQ = primaryBh[i];
    r.primaryByQ = primaryBy[i];
    r.signTestBhQ = signBh[i];
    r.subsetABhQ = subsetABh[i];
    r.subsetBBhQ = subsetBBh[i];
    r.subsetASignBhQ = subsetASignBh[i];
    r.subsetBSignBhQ = subsetBSignBh[i];
    const sourceQ = asNumber(r.source.bh_q, "bh_q");
    validation.maxPrimaryBhQDiff = Math.max(validation.maxPrimaryBhQDiff, Math.abs(r.primaryBhQ - sourceQ));
    if (!near(r.primaryBhQ, sourceQ)) throw new Error(`${r.source.hypothesis_id}: recomputed primary BH q does not match relation evidence`);
  });
  familyResults[family] = results;
}

const primarySupported = Object.values(familyResults).flat().filter(r => r.primaryBhQ < ALPHA);
if (familyResults.single_scale.filter(r => r.primaryBhQ < ALPHA).length !== 27) throw new Error("Primary single-scale supported count is not 27");
if (familyResults.all_scales.filter(r => r.primaryBhQ < ALPHA).length !== 14) throw new Error("Primary all-scale supported count is not 14");

const outputRows = primarySupported.map(r => {
  const bootstrapLow = asNumber(r.source.bootstrap_mean_CI95_low, "bootstrap_mean_CI95_low");
  const bootstrapHigh = asNumber(r.source.bootstrap_mean_CI95_high, "bootstrap_mean_CI95_high");
  const looMin = asNumber(r.source.LOO_minimum_mean_D, "LOO_minimum_mean_D");
  const metrics = {
    bySupported: r.primaryByQ < ALPHA,
    signTestSupported: r.signTestBhQ < ALPHA,
    subsetAMean: r.a.mean,
    subsetBMean: r.b.mean,
    subsetAMedian: r.a.median,
    subsetBMedian: r.b.median,
    looMin,
    bootstrapLow,
  };
  return {
    family: r.family === "single_scale" ? "single-scale" : "all-scale",
    hypothesis: relationLabel(r.source),
    primary_mean_D: r.primary.mean,
    primary_median_D: r.primary.median,
    primary_positive_count: r.primary.positive,
    primary_N_tests: 14,
    primary_positive_over_14: `${r.primary.positive}/14`,
    primary_exact_signflip_p: r.primary.signflipP,
    primary_BH_q: r.primaryBhQ,
    primary_signflip_BY_q: r.primaryByQ,
    BY_supported: r.primaryByQ < ALPHA,
    exact_sign_test_p: r.primary.signTestP,
    sign_test_N_effective: r.primary.signTestNEffective,
    sign_test_zero_count: r.primary.zero,
    sign_test_BH_q: r.signTestBhQ,
    sign_test_BH_supported: r.signTestBhQ < ALPHA,
    subset_A_mean_D: r.a.mean,
    subset_A_median_D: r.a.median,
    subset_A_positive_count: r.a.positive,
    subset_A_N_tests: 7,
    subset_A_positive_over_7: `${r.a.positive}/7`,
    subset_A_exact_signflip_p: r.a.signflipP,
    subset_A_BH_q: r.subsetABhQ,
    subset_A_sign_test_p: r.a.signTestP,
    subset_A_sign_test_BH_q: r.subsetASignBhQ,
    subset_B_mean_D: r.b.mean,
    subset_B_median_D: r.b.median,
    subset_B_positive_count: r.b.positive,
    subset_B_N_tests: 7,
    subset_B_positive_over_7: `${r.b.positive}/7`,
    subset_B_exact_signflip_p: r.b.signflipP,
    subset_B_BH_q: r.subsetBBhQ,
    subset_B_sign_test_p: r.b.signTestP,
    subset_B_sign_test_BH_q: r.subsetBSignBhQ,
    LOO_minimum_mean_D: looMin,
    bootstrap_mean_CI95_low: bootstrapLow,
    bootstrap_mean_CI95_high: bootstrapHigh,
    audit_classification: auditClassification(metrics),
  };
});

const outputHeaders = [
  "family", "hypothesis", "primary_mean_D", "primary_median_D", "primary_positive_count", "primary_N_tests", "primary_positive_over_14",
  "primary_exact_signflip_p", "primary_BH_q", "primary_signflip_BY_q", "BY_supported", "exact_sign_test_p", "sign_test_N_effective", "sign_test_zero_count", "sign_test_BH_q", "sign_test_BH_supported",
  "subset_A_mean_D", "subset_A_median_D", "subset_A_positive_count", "subset_A_N_tests", "subset_A_positive_over_7", "subset_A_exact_signflip_p", "subset_A_BH_q", "subset_A_sign_test_p", "subset_A_sign_test_BH_q",
  "subset_B_mean_D", "subset_B_median_D", "subset_B_positive_count", "subset_B_N_tests", "subset_B_positive_over_7", "subset_B_exact_signflip_p", "subset_B_BH_q", "subset_B_sign_test_p", "subset_B_sign_test_BH_q",
  "LOO_minimum_mean_D", "bootstrap_mean_CI95_low", "bootstrap_mean_CI95_high", "audit_classification",
];
const outputCsv = toCsv(outputHeaders, outputRows);

// Artifact-tool round-trip validation of the authored CSV before writing the requested output.
const csvWorkbook = await Workbook.fromCSV(outputCsv, { sheetName: "Supported sensitivity" });
const csvInspection = await csvWorkbook.inspect({
  kind: "table",
  range: `Supported sensitivity!A1:AL${outputRows.length + 1}`,
  include: "values",
  tableMaxRows: 3,
  tableMaxCols: outputHeaders.length,
  maxChars: 8000,
});
if (!csvInspection?.ndjson || outputRows.length !== 41) throw new Error("Artifact-tool CSV verification failed");

function familySummary(results) {
  return {
    primaryBh: countIf(results, r => r.primaryBhQ < ALPHA),
    zeroDObservations: results.reduce((sum, r) => sum + r.primary.zero, 0),
    hypothesesWithZeroD: countIf(results, r => r.primary.zero > 0),
    minSignTestNEffective: Math.min(...results.map(r => r.primary.signTestNEffective)),
    signRaw: countIf(results, r => r.primary.signTestP < ALPHA),
    signBh: countIf(results, r => r.signTestBhQ < ALPHA),
    minSignRaw: Math.min(...results.map(r => r.primary.signTestP)),
    minSignBh: Math.min(...results.map(r => r.signTestBhQ)),
    by: countIf(results, r => r.primaryByQ < ALPHA),
    minBy: Math.min(...results.map(r => r.primaryByQ)),
    subsetABh: countIf(results, r => r.subsetABhQ < ALPHA),
    subsetBBh: countIf(results, r => r.subsetBBhQ < ALPHA),
    subsetASignRaw: countIf(results, r => r.a.signTestP < ALPHA),
    subsetASignBh: countIf(results, r => r.subsetASignBhQ < ALPHA),
    subsetBSignRaw: countIf(results, r => r.b.signTestP < ALPHA),
    subsetBSignBh: countIf(results, r => r.subsetBSignBhQ < ALPHA),
  };
}

const singleSummary = familySummary(familyResults.single_scale);
const allSummary = familySummary(familyResults.all_scales);
const diagA = intervalDiagnostics(SUBSET_A);
const diagB = intervalDiagnostics(SUBSET_B);
const bothMeansPositive = countIf(outputRows, r => r.subset_A_mean_D > 0 && r.subset_B_mean_D > 0);
const bothMediansPositive = countIf(outputRows, r => r.subset_A_median_D > 0 && r.subset_B_median_D > 0);
const meanHalfReversals = outputRows.filter(r => r.subset_A_mean_D <= 0 || r.subset_B_mean_D <= 0);
const severeTemporalReversals = outputRows.filter(r =>
  (r.subset_A_mean_D <= 0 && r.subset_A_median_D <= 0) ||
  (r.subset_B_mean_D <= 0 && r.subset_B_median_D <= 0)
);
const primaryMedianNonpositive = outputRows.filter(r => r.primary_median_D <= 0);
const byUnsupported = outputRows.filter(r => !r.BY_supported);
const signBhUnsupported = outputRows.filter(r => !r.sign_test_BH_supported);
const classifications = Object.fromEntries(["STABLE UNDER SENSITIVITY", "MIXED SENSITIVITY", "DEPENDENCE-SENSITIVE"].map(label => [label, countIf(outputRows, r => r.audit_classification === label)]));
const seriousContradictions = outputRows.filter(r => {
  const directionalSignConflict = r.primary_median_D <= 0;
  const temporalDirectionConflict = (r.subset_A_mean_D <= 0 && r.subset_A_median_D <= 0) || (r.subset_B_mean_D <= 0 && r.subset_B_median_D <= 0);
  return directionalSignConflict || temporalDirectionConflict;
});

function relationList(rows) {
  return rows.length ? rows.map(r => `\`${r.hypothesis}\``).join(', ') : "none";
}

const report = `# MSGNet Statistical Freeze Audit

Audit date: 2026-08-30  
Scope: statistical sensitivity/freeze audit only; no model inference, website edits, test reselection, hypothesis reselection, primary-result replacement, or file deletion.

## Data lineage and integrity checks

- Numeric sources were limited to \`case_evidence.csv\`, \`relation_evidence_single_scale.csv\`, and \`relation_evidence_all_scale.csv\` under \`artifacts/msgnet_cross_test_v1/\`.
- The available case/relation evidence artifacts are CSV files (with JSON-encoded fields such as control relation lists); no same-named case/relation JSON artifact was present. No prediction arrays or model runtime files were read.
- Case rows: 2,352 = 126 single-scale hypotheses × 14 tests + 42 all-scale hypotheses × 14 tests.
- Frozen test IDs observed exactly: ${TEST_IDS.join(', ')}.
- Recomputed primary mean, median, sign counts, exact sign-flip p, and BH q matched the existing relation evidence. Maximum absolute differences were: mean ${validation.maxMeanDiff.toExponential(3)}, median ${validation.maxMedianDiff.toExponential(3)}, sign-flip p ${validation.maxSignflipPDiff.toExponential(3)}, BH q ${validation.maxPrimaryBhQDiff.toExponential(3)}.

## Methods frozen for this audit

The formal PRIMARY remains the one-sided exact sign-flip test on mean D with the existing family-wise BH correction (126 single-scale; 42 all-scale). No sensitivity result replaces it.

- Exact sign test: one-sided H1 that the sign/median tendency is positive. Zeros are omitted from the binomial trial count and recorded separately; p = P[Binomial(n_nonzero, 0.5) ≥ n_positive].
- BY sensitivity: Benjamini–Yekutieli applied to the existing/recomputed PRIMARY exact sign-flip raw p values separately within the 126- and 42-hypothesis families.
- Temporal sensitivity: deterministic interleaved subsets fixed solely by frozen-list position, followed by the same one-sided exact sign-flip test and separate BH within each family/subset. Exact sign-test BH was also computed as sensitivity.
- Exact inequalities use p/q < 0.05, matching the requested wording.

## A. Exact sign-test sensitivity (14 tests)

| family | family size | zero-D observations | hypotheses with zero D | minimum nonzero n | raw p < .05 | BH q < .05 | minimum raw p | minimum BH q |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| single-scale | 126 | ${singleSummary.zeroDObservations} | ${singleSummary.hypothesesWithZeroD} | ${singleSummary.minSignTestNEffective} | ${singleSummary.signRaw} | ${singleSummary.signBh} | ${formatP(singleSummary.minSignRaw)} | ${formatP(singleSummary.minSignBh)} |
| all-scale | 42 | ${allSummary.zeroDObservations} | ${allSummary.hypothesesWithZeroD} | ${allSummary.minSignTestNEffective} | ${allSummary.signRaw} | ${allSummary.signBh} | ${formatP(allSummary.minSignRaw)} | ${formatP(allSummary.minSignBh)} |

## B. Benjamini–Yekutieli sensitivity on PRIMARY sign-flip p

| family | BY-supported q < .05 | minimum BY q |
|---|---:|---:|
| single-scale | ${singleSummary.by} | ${formatP(singleSummary.minBy)} |
| all-scale | ${allSummary.by} | ${formatP(allSummary.minBy)} |

This is dependence-robust multiplicity sensitivity only. The original PRIMARY BH result remains unchanged.

## C. Temporal-separation sensitivity

Subset A IDs (frozen positions 1,3,5,7,9,11,13): **${SUBSET_A.join(', ')}**  
Subset B IDs (frozen positions 2,4,6,8,10,12,14): **${SUBSET_B.join(', ')}**

Raw span is fixed at 192 hours for this audit, inferred deterministically from the supplied frozen-design statement that a 214-hour adjacent start gap leaves about 22 hours unused; intervals are represented as \`[start, start+191]\`. Raw span is not a separate column in the permitted case/relation CSV sources. “Minimum gap” below is the unused gap between raw blocks; start-gap minima are also shown to remove ambiguity.

| subset | raw span | start-gap sequence | minimum start gap | unused-gap sequence | minimum unused gap | overlap count |
|---|---:|---|---:|---|---:|---:|
| A | ${diagA.rawSpan} h | ${diagA.startGaps.join('/')} h | ${diagA.minStartGap} h | ${diagA.unusedGaps.join('/')} h | ${diagA.minUnusedGap} h | ${diagA.overlapCount} |
| B | ${diagB.rawSpan} h | ${diagB.startGaps.join('/')} h | ${diagB.minStartGap} h | ${diagB.unusedGaps.join('/')} h | ${diagB.minUnusedGap} h | ${diagB.overlapCount} |

### Subset exact sign-flip + BH results

| subset | single-scale BH supported | all-scale BH supported |
|---|---:|---:|
| A | ${singleSummary.subsetABh} | ${allSummary.subsetABh} |
| B | ${singleSummary.subsetBBh} | ${allSummary.subsetBBh} |

### Subset exact sign-test sensitivity

| subset | family | raw p < .05 | BH q < .05 |
|---|---|---:|---:|
| A | single-scale | ${singleSummary.subsetASignRaw} | ${singleSummary.subsetASignBh} |
| A | all-scale | ${allSummary.subsetASignRaw} | ${allSummary.subsetASignBh} |
| B | single-scale | ${singleSummary.subsetBSignRaw} | ${singleSummary.subsetBSignBh} |
| B | all-scale | ${allSummary.subsetBSignRaw} | ${allSummary.subsetBSignBh} |

The n=7 subset BH results are temporal sensitivity only and are not gates for retaining a 14-test PRIMARY-supported relation.

## D. Stability of the 41 PRIMARY-supported relations

- PRIMARY-supported relations with mean D > 0 in both A and B: **${bothMeansPositive}/41**.
- PRIMARY-supported relations with median D > 0 in both A and B: **${bothMediansPositive}/41**.
- Any subset mean D ≤ 0: **${meanHalfReversals.length}/41** (${relationList(meanHalfReversals)}).
- Severe temporal-half direction reversal (a half has both mean D ≤ 0 and median D ≤ 0): **${severeTemporalReversals.length}/41** (${relationList(severeTemporalReversals)}).
- PRIMARY median D ≤ 0: **${primaryMedianNonpositive.length}/41** (${relationList(primaryMedianNonpositive)}).
- Exact sign-test BH unsupported among PRIMARY-supported: **${signBhUnsupported.length}/41**.
- BY unsupported among PRIMARY-supported: **${byUnsupported.length}/41** (${relationList(byUnsupported)}).

The complete 41-row stability table, with every requested primary/sign-test/BY/subset/LOO/bootstrap field, is in \`msgnet_supported_sensitivity.csv\`.

## E. Audit-only classification

Uniform rules were defined in code without hypothesis/edge names:

1. **DEPENDENCE-SENSITIVE** if PRIMARY BY q is not < .05.
2. Otherwise **STABLE UNDER SENSITIVITY** if 14-test sign-test BH q < .05, both subset means and medians are > 0, LOO minimum mean > 0, and bootstrap mean CI low > 0.
3. Otherwise **MIXED SENSITIVITY**.

| audit-only label | count |
|---|---:|
| STABLE UNDER SENSITIVITY | ${classifications["STABLE UNDER SENSITIVITY"]} |
| MIXED SENSITIVITY | ${classifications["MIXED SENSITIVITY"]} |
| DEPENDENCE-SENSITIVE | ${classifications["DEPENDENCE-SENSITIVE"]} |

These labels are audit-only and were not written to any production website JSON.

## Final answers

1. **Q1. PRIMARY single-scale BH supported:** ${singleSummary.primaryBh}.
2. **Q2. PRIMARY all-scale BH supported:** ${allSummary.primaryBh}.
3. **Q3. Sign-test BH supported:** single = ${singleSummary.signBh}; all = ${allSummary.signBh}.
4. **Q4. BY supported:** single = ${singleSummary.by}; all = ${allSummary.by}.
5. **Q5. Subset A sign-flip BH supported:** single = ${singleSummary.subsetABh}; all = ${allSummary.subsetABh}.
6. **Q6. Subset B sign-flip BH supported:** single = ${singleSummary.subsetBBh}; all = ${allSummary.subsetBBh}.
7. **Q7. PRIMARY-supported relations with mean D > 0 in both A and B:** ${bothMeansPositive}/41.
8. **Q8. Obvious temporal-half reversal:** ${severeTemporalReversals.length === 0 ? "No" : "Yes"}; ${severeTemporalReversals.length} relation(s) met the predeclared severe-reversal rule. Relations with any nonpositive half mean: ${meanHalfReversals.length}.
9. **Q9. Severe contradiction across sign tendency or temporal split:** ${seriousContradictions.length === 0 ? "None found" : `Found ${seriousContradictions.length}: ${relationList(seriousContradictions)}`}. BY non-support is reported separately as dependence sensitivity (${byUnsupported.length}), not treated by itself as a directional contradiction.
10. **Q10. Freeze decision:** ${seriousContradictions.length === 0 ? "Yes—statistics can be frozen for website migration, while preserving the original 14-test sign-flip + BH analysis as PRIMARY and carrying audit-only sensitivity labels only in these audit artifacts." : "No automatic freeze recommendation; review the listed directional contradictions before migration."}
`;

await fs.writeFile(CSV_PATH, outputCsv, "utf8");
await fs.writeFile(REPORT_PATH, report, "utf8");

const verification = {
  sources: { cases: cases.length, singleRelations: relationRows.single_scale.length, allRelations: relationRows.all_scales.length },
  frozenTestIds: observedTestIds,
  summaries: { single: singleSummary, all: allSummary },
  primarySupportedRows: outputRows.length,
  bothMeansPositive,
  bothMediansPositive,
  meanHalfReversals: meanHalfReversals.map(r => r.hypothesis),
  severeTemporalReversals: severeTemporalReversals.map(r => r.hypothesis),
  seriousContradictions: seriousContradictions.map(r => r.hypothesis),
  byUnsupported: byUnsupported.map(r => r.hypothesis),
  classifications,
  validation,
  artifactToolVerified: true,
};
console.log(JSON.stringify(verification, null, 2));
