type Tone = 'primary' | 'secondary' | 'ghost';

const toneClasses: Record<Tone, string> = {
  primary: 'bg-[#b54434] border-[#962a24] text-[#fffdf9] hover:bg-[#a03b2d]',
  secondary: 'bg-[#173152] border-[#102947] text-[#f8fbff] hover:bg-[#1e3d66]',
  ghost: 'bg-[#f1f5fa] border-[#cbd7e6] text-[#14304d] hover:bg-[#e2eaf5]',
};

type Props = {
  busy?: boolean;
  disabled?: boolean;
  label: string;
  onClick: () => void;
  tone?: Tone;
};

export function ActionButton({ busy = false, disabled = false, label, onClick, tone = 'primary' }: Props) {
  return (
    <button
      disabled={disabled || busy}
      onClick={onClick}
      className={[
        'inline-flex items-center justify-center gap-2.5 rounded-2xl border px-4 py-3 min-h-[52px]',
        'text-sm font-extrabold tracking-wide',
        'transition-all duration-100 active:scale-[0.985] cursor-pointer',
        'disabled:opacity-55 disabled:cursor-not-allowed',
        toneClasses[tone],
      ].join(' ')}
    >
      {busy && (
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {label}
    </button>
  );
}
