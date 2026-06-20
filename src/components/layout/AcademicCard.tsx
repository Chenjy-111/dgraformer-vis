import { type ReactNode } from 'react';

export function AcademicCard({
  title,
  index,
  children,
}: {
  title: string;
  index?: string;
  children?: ReactNode;
}) {
  return (
    <div className="card p-4">
      {index && <div className="data-num mb-2 text-[11px] text-ink-400">{index}</div>}
      <h4 className="text-[14px] font-semibold text-ink-900">{title}</h4>
      <div className="mt-2">{children}</div>
    </div>
  );
}
