import { type Page } from "@playwright/test";

export async function devLogin(page: Page, username: string) {
  await page.goto("/");
  await page.getByRole("button", { name: /more options/i }).click();
  await page.getByPlaceholder("player-one").fill(username);
  await page.getByRole("button", { name: /continue as guest/i }).click();
  await page.waitForURL("**/lobby");
}
