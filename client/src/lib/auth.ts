import { Platform } from "react-native";

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
    if (Platform.OS !== "web") {
        throw new Error(
            "Google login is currently available in the web client only.",
        );
    }

    const browserWindow = globalThis as Window & typeof globalThis;
    const expectedOrigin = new URL(baseUrl).origin;
    const left = Math.max(
        0,
        browserWindow.screenX + (browserWindow.outerWidth - POPUP_WIDTH) / 2,
    );
    const top = Math.max(
        0,
        browserWindow.screenY + (browserWindow.outerHeight - POPUP_HEIGHT) / 2,
    );
    const popup = browserWindow.open(
        `${baseUrl}/auth/google/login`,
        "setback-google-login",
        `popup=yes,width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${left},top=${top}`,
    );

    if (!popup) {
        throw new Error(
            "Allow popups for this site to continue with Google login.",
        );
    }

    const loginWindow = popup;

    return new Promise<TokenResponse>((resolve, reject) => {
        const timeoutId = browserWindow.setTimeout(
            () => {
                cleanup();
                reject(new Error("Google login timed out. Please try again."));
            },
            2 * 60 * 1000,
        );

        function handleMessage(event: MessageEvent) {
            if (event.origin !== expectedOrigin) {
                return;
            }
            if (event.source !== loginWindow) {
                return;
            }
            if (!isTokenResponse(event.data)) {
                return;
            }
            cleanup();
            resolve(event.data);
        }

        browserWindow.addEventListener("message", handleMessage);

        function cleanup() {
            browserWindow.removeEventListener("message", handleMessage);
            browserWindow.clearTimeout(timeoutId);
            // No loginWindow.close() here: the popup's inline script runs
            // window.close() on itself after postMessage, and calling it
            // from the opener would trigger a COOP console warning.
        }
    });
}
