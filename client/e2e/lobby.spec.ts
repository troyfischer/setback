import { test, expect, type Page } from "@playwright/test";
import { devLogin } from "./helpers";

test("guest can log in and see the lobby", async ({ page }) => {
  await devLogin(page, `test-${Date.now()}`);
  await expect(page.getByRole("heading", { name: /setback/i })).toBeVisible();
});

test("owner can create a game and see join code", async ({ page }) => {
  await devLogin(page, `owner-${Date.now()}`);
  await page.getByRole("button", { name: /create game/i }).click();
  await expect(page.getByText(/share this join code/i)).toBeVisible();
});

test("owner sees delete game button after creating a game", async ({
  page,
}) => {
  await devLogin(page, `owner-${Date.now()}`);
  await page.getByRole("button", { name: /create game/i }).click();
  await expect(
    page.getByRole("button", { name: /delete game/i }),
  ).toBeVisible();
});

test("second player can join via code and both see the lobby", async ({
  browser,
}) => {
  const ownerCtx = await browser.newContext();
  const memberCtx = await browser.newContext();
  const ownerPage: Page = await ownerCtx.newPage();
  const memberPage: Page = await memberCtx.newPage();

  const ts = Date.now();
  await devLogin(ownerPage, `owner-${ts}`);
  await devLogin(memberPage, `member-${ts}`);

  // Owner creates game
  await ownerPage.getByRole("button", { name: /create game/i }).click();
  const codeText = await ownerPage.getByText(/\d+-\w+/).textContent();
  const joinCode = codeText?.trim() ?? "";

  // Member joins
  await memberPage.getByPlaceholder(/abc123/i).fill(joinCode);
  await memberPage.getByRole("button", { name: /join game/i }).click();

  // Both should see the table
  await expect(ownerPage.getByText(/game #/i)).toBeVisible();
  await expect(memberPage.getByText(/game #/i)).toBeVisible();

  await ownerCtx.close();
  await memberCtx.close();
});
