import { formatCard } from "../lib/format";
import type { SetbackCard } from "../types/setback";

type Props = {
  busy?: boolean;
  card: SetbackCard;
  caption?: string;
  disabled?: boolean;
  onPress?: () => void;
};

export function PlayingCard({ busy, card, caption, disabled, onPress }: Props) {
  const isRed = card.suit === "heart" || card.suit === "diamond";
  const label = formatCard(card);

  const inner = (
    <div
      className={[
        "flex flex-col items-center justify-center rounded-2xl border",
        "bg-white border-slate-200 shadow-md",
        "min-h-[86px] min-w-[64px] px-3 py-2.5",
        busy ? "opacity-70" : "",
      ].join(" ")}
    >
      <span
        className={[
          "text-2xl font-extrabold tracking-wide",
          isRed ? "text-[#b43c2a]" : "text-[#0d1d31]",
        ].join(" ")}
      >
        {label}
      </span>
      {caption && (
        <span className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-[#5c7593]">
          {caption}
        </span>
      )}
    </div>
  );

  if (!onPress) return inner;

  return (
    <button
      data-testid="playing-card"
      disabled={disabled || busy}
      onClick={onPress}
      className={[
        "transition-transform duration-100",
        "hover:scale-105 active:scale-95",
        "disabled:opacity-45 disabled:cursor-not-allowed disabled:scale-100",
        "cursor-pointer",
      ].join(" ")}
    >
      {inner}
    </button>
  );
}
