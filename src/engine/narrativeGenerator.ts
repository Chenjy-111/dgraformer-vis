import type { Explanation } from '@/types/explanation';

export function explanationToMarkdown(e: Explanation): string {
  const lines = [`# ${e.title}`, '', `*${e.selectionLabel}*`, '', e.summary, ''];
  if (e.evidence.length) {
    lines.push('## Evidence', '');
    for (const ev of e.evidence) lines.push(`- **${ev.label}:** ${ev.value}`);
    lines.push('');
  }
  if (e.formula) lines.push('## Formula', '', e.formula.replace(/<[^>]*>/g, ''), '');
  if (e.assumption) lines.push('## Assumption', '', e.assumption, '');
  if (e.caveat) lines.push('## Caveat', '', e.caveat, '');
  if (e.nextStep) lines.push('## Suggested next step', '', e.nextStep, '');
  return lines.join('\n');
}

export function download(filename: string, content: string, type = 'text/plain') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
