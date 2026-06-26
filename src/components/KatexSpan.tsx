import { useMemo } from 'react';
import { prender } from '@/utils/katexPrender';

export function KatexSpan({
  tex,
  html: preRendered,
  block,
}: {
  tex?: string;
  html?: string;
  block?: boolean;
}) {
  const result = useMemo(() => {
    if (preRendered) return preRendered;
    if (tex) return prender(tex, !!block);
    return null;
  }, [tex, preRendered, block]);

  if (!result) return null;

  return (
    <span
      className={block ? 'block-formula' : 'inline-formula'}
      dangerouslySetInnerHTML={{ __html: result }}
    />
  );
}
