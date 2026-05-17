import { useCallback, useRef, useState } from "react";

import type { ToastItem, ToastKind } from "../components/Toast";

export function useToasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const pushToast = useCallback((kind: ToastKind, message: string) => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, kind, message }]);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return {
    toasts,
    dismissToast,
    notice: (message: string) => pushToast("notice", message),
    error: (message: string) => pushToast("error", message),
  };
}
