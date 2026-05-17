import { useEffect, useState } from "react";

export type ToastKind = "notice" | "error";

export type ToastItem = {
  id: number;
  kind: ToastKind;
  message: string;
};

type Props = {
  toast: ToastItem;
  onDismiss: (id: number) => void;
};

const DISMISS_MS = 3500;
const EXIT_MS = 250;

function Toast({ toast, onDismiss }: Props) {
  const [entered, setEntered] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    // Trigger enter animation on mount
    const enterId = requestAnimationFrame(() => setEntered(true));
    const dismissId = setTimeout(() => {
      setLeaving(true);
      setTimeout(() => onDismiss(toast.id), EXIT_MS);
    }, DISMISS_MS);
    return () => {
      cancelAnimationFrame(enterId);
      clearTimeout(dismissId);
    };
  }, [toast.id, onDismiss]);

  const base =
    "rounded-2xl border px-4 py-3 shadow-lg transition-all duration-200 ease-out min-w-[220px] max-w-sm";
  const colors =
    toast.kind === "error"
      ? "bg-red-50 border-red-200/60 dark:bg-red-game/[0.95] dark:border-red-game/40"
      : "bg-emerald-50 border-emerald-200/60 dark:bg-emerald-600/[0.95] dark:border-emerald-500/40";
  const textColors =
    toast.kind === "error"
      ? "text-red-700 dark:text-white"
      : "text-emerald-700 dark:text-white";

  const transform = leaving
    ? "translate-x-8 opacity-0"
    : entered
      ? "translate-x-0 opacity-100"
      : "translate-x-8 opacity-0";

  return (
    <div className={`${base} ${colors} ${transform}`}>
      <p className={`text-sm font-semibold ${textColors}`}>{toast.message}</p>
    </div>
  );
}

type ContainerProps = {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
};

export function ToastContainer({ toasts, onDismiss }: ContainerProps) {
  return (
    <div className="pointer-events-none fixed top-5 right-5 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <Toast toast={t} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}
