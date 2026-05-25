import { apiBaseUrl } from "./api";
import type { TokenResponse } from "../types/setback";

const POPUP_WIDTH = 520;
const POPUP_HEIGHT = 720;

function isTokenResponse(value: unknown): value is TokenResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "access_token" in value &&
    typeof (value as { access_token?: unknown }).access_token === "string"
  );
}

export async function loginWithGoogle(baseUrl: string): Promise<TokenResponse> {
  const expectedOrigin = new URL(baseUrl).origin;
  const left = Math.max(
    0,
    window.screenX + (window.outerWidth - POPUP_WIDTH) / 2,
  );
  const top = Math.max(
    0,
    window.screenY + (window.outerHeight - POPUP_HEIGHT) / 2,
  );
  const popup = window.open(
    `${apiBaseUrl(baseUrl)}/auth/google/login`,
    "setback-google-login",
    `popup=yes,width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${left},top=${top}`,
  );

  if (!popup) {
    throw new Error(
      "Allow popups for this site to continue with Google login.",
    );
  }

  return new Promise<TokenResponse>((resolve, reject) => {
    const timeoutId = window.setTimeout(
      () => {
        cleanup();
        reject(new Error("Google login timed out. Please try again."));
      },
      2 * 60 * 1000,
    );

    function handleMessage(event: MessageEvent) {
      if (event.origin !== expectedOrigin) return;
      if (event.source !== popup) return;
      if (!isTokenResponse(event.data)) return;
      cleanup();
      resolve(event.data);
    }

    window.addEventListener("message", handleMessage);

    function cleanup() {
      window.removeEventListener("message", handleMessage);
      window.clearTimeout(timeoutId);
    }
  });
}
