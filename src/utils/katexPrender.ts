import katex from 'katex';

export function prender(tex: string, displayMode = true): string {
  try {
    return katex.renderToString(tex, {
      throwOnError: true,
      displayMode,
      strict: 'warn',
    });
  } catch (e) {
    console.error('[KaTeX] Pre-render failed:', tex, e);
    return `<span class="formula-error" style="color:#d32f2f;cursor:help" title="${tex}">[公式渲染失败]</span>`;
  }
}
