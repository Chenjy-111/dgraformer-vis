import { useMemo } from 'react';
import katex from 'katex';

export function KatexSpan({ tex, block }: { tex: string; block?: boolean }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(tex, { throwOnError: false, displayMode: !!block });
    } catch {
      return tex;
    }
  }, [tex, block]);
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}
