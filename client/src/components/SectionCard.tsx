import type { ReactNode } from 'react';

type Props = {
  children: ReactNode;
  eyebrow?: string;
  subtitle?: string;
  title: string;
};

export function SectionCard({ children, eyebrow, subtitle, title }: Props) {
  return (
    <div className="rounded-3xl bg-[#fffaf2] px-5 py-5 shadow-xl flex flex-col gap-2">
      {eyebrow && (
        <span className="text-xs font-extrabold uppercase tracking-[1.6px] text-[#b54434]">{eyebrow}</span>
      )}
      <h2 className="text-2xl font-extrabold text-[#102947]">{title}</h2>
      {subtitle && <p className="text-sm leading-relaxed text-[#536983] mb-1">{subtitle}</p>}
      <div className="flex flex-col gap-3.5">{children}</div>
    </div>
  );
}
