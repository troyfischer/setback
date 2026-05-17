type Tone = "primary" | "secondary" | "ghost" | "danger";

const toneClasses: Record<Tone, string> = {
  primary: [
    "bg-red-game border-red-game-dark text-white hover:bg-red-game-dark",
    "dark:bg-red-game/75 dark:border-red-game/30 dark:backdrop-blur-sm dark:hover:bg-red-game/95",
    "dark:shadow-lg dark:shadow-red-game/20",
  ].join(" "),
  secondary: [
    "bg-navy-800 border-navy-900 text-sky-50 hover:bg-navy-700",
    "dark:bg-navy-700/55 dark:border-white/10 dark:text-blue-50 dark:hover:bg-navy-600/65 dark:backdrop-blur-sm",
  ].join(" "),
  ghost: [
    "bg-white/70 border-slate-200/80 text-slate-700 hover:bg-white/95 backdrop-blur-sm",
    "dark:bg-white/[0.07] dark:border-white/[0.11] dark:text-blue-100 dark:hover:bg-white/[0.13]",
  ].join(" "),
  danger: [
    "bg-red-500 border-red-600 text-white hover:bg-red-400",
    "dark:bg-red-500/70 dark:border-red-500/30 dark:backdrop-blur-sm dark:hover:bg-red-500/90",
  ].join(" "),
};

type Props = {
  busy?: boolean;
  disabled?: boolean;
  label: string;
  onClick: () => void;
  tone?: Tone;
};

export function ActionButton({
  busy = false,
  disabled = false,
  label,
  onClick,
  tone = "primary",
}: Props) {
  return (
    <button
      disabled={disabled || busy}
      onClick={onClick}
      className={[
        "inline-flex items-center justify-center gap-2.5 rounded-2xl border px-4 py-3 min-h-[52px]",
        "text-sm font-extrabold tracking-wide",
        "transition-all duration-150 active:scale-[0.985] cursor-pointer",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        toneClasses[tone],
      ].join(" ")}
    >
      {busy && (
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {label}
    </button>
  );
}
