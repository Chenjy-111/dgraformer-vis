import { type ReactNode } from 'react';

export function Section({
  children,
  id,
  className,
  eyebrow,
  title,
  intro,
}: {
  children: ReactNode;
  id?: string;
  className?: string;
  eyebrow?: string;
  title?: string;
  intro?: string;
}) {
  return (
    <section id={id} className={`border-b border-line bg-white px-5 py-14 ${className ?? ''}`}>
      <div className="mx-auto max-w-[1400px]">
        {eyebrow && <div className="eyebrow mb-3">{eyebrow}</div>}
        {title && <h2 className="font-serif text-[28px] font-semibold leading-tight">{title}</h2>}
        {intro && <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-500">{intro}</p>}
        {(eyebrow || title || intro) && <div className="mt-8">{children}</div>}
        {!eyebrow && !title && !intro && children}
      </div>
    </section>
  );
}
