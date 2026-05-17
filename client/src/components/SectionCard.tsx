import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  eyebrow?: string;
  subtitle?: string;
  title: string;
};

export function SectionCard({ children, eyebrow, subtitle, title }: Props) {
  return (
    <div className="rounded-3xl backdrop-blur-xl border shadow-xl px-5 py-5 flex flex-col gap-2 bg-white/[0.65] border-white/75 shadow-black/[0.04] dark:bg-white/[0.06] dark:border-white/[0.10] dark:shadow-black/50">
      {eyebrow && (
        <span className="text-xs font-extrabold uppercase tracking-[1.6px] text-red-game">
          {eyebrow}
        </span>
      )}
      <h2 className="text-2xl font-extrabold text-gray-900 dark:text-white">
        {title}
      </h2>
      {subtitle && (
        <p className="text-sm leading-relaxed text-slate-500 dark:text-blue-200/70 mb-1">
          {subtitle}
        </p>
      )}
      <div className="flex flex-col gap-3.5">{children}</div>
    </div>
  );
}
