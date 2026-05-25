import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";

export async function devLogin(page: Page, username: string) {
  await page.goto("/");
  await page.getByRole("button", { name: /more options/i }).click();
  await page.getByPlaceholder("player-one").fill(username);
  await page.getByRole("button", { name: /continue as guest/i }).click();
  await page.waitForURL("**/lobby");
}

export type TwoPlayerLobbySetup = {
  joinCode: string;
  memberCtx: BrowserContext;
  memberPage: Page;
  ownerCtx: BrowserContext;
  ownerPage: Page;
};

export async function setupTwoPlayerLobby(
  browser: Browser,
  ts = Date.now(),
): Promise<TwoPlayerLobbySetup> {
  const ownerCtx = await browser.newContext();
  const memberCtx = await browser.newContext();
  const ownerPage = await ownerCtx.newPage();
  const memberPage = await memberCtx.newPage();

  await devLogin(ownerPage, `owner-${ts}`);
  await devLogin(memberPage, `member-${ts}`);

  await ownerPage.getByRole("button", { name: /create game/i }).click();
  const codeEl = ownerPage.locator("p.font-mono");
  await expect(codeEl).toBeVisible();
  const joinCode = ((await codeEl.textContent()) ?? "").trim();

  await memberPage.getByPlaceholder(/abc123/i).fill(joinCode);
  await memberPage.getByRole("button", { name: /join game/i }).click();

  await ownerPage.waitForURL(`**/lobby/${joinCode}`, { timeout: 15000 });
  await memberPage.waitForURL(`**/lobby/${joinCode}`, { timeout: 15000 });

  return {
    joinCode,
    memberCtx,
    memberPage,
    ownerCtx,
    ownerPage,
  };
}

export type InProgressGameSetup = {
  contexts: BrowserContext[];
  joinCode: string;
  ownerPage: Page;
  pages: Page[];
};

export async function setupInProgressGame(
  browser: Browser,
  ts = Date.now(),
): Promise<InProgressGameSetup> {
  const contexts = await Promise.all(
    ["owner", "member-a", "member-b", "member-c"].map(() =>
      browser.newContext(),
    ),
  );
  const [ownerCtx, memberACtx, memberBCtx, memberCCtx] = contexts;
  const ownerPage = await ownerCtx.newPage();
  const memberAPage = await memberACtx.newPage();
  const memberBPage = await memberBCtx.newPage();
  const memberCPage = await memberCCtx.newPage();
  const pages = [ownerPage, memberAPage, memberBPage, memberCPage];

  await devLogin(ownerPage, `owner-${ts}`);
  await devLogin(memberAPage, `member-a-${ts}`);
  await devLogin(memberBPage, `member-b-${ts}`);
  await devLogin(memberCPage, `member-c-${ts}`);

  await ownerPage.getByRole("button", { name: /create game/i }).click();
  const codeEl = ownerPage.locator("p.font-mono");
  await expect(codeEl).toBeVisible();
  const joinCode = ((await codeEl.textContent()) ?? "").trim();

  for (const page of [memberAPage, memberBPage, memberCPage]) {
    await page.getByPlaceholder(/abc123/i).fill(joinCode);
    await page.getByRole("button", { name: /join game/i }).click();
    await page.waitForURL(`**/lobby/${joinCode}`, { timeout: 15000 });
  }

  const teamGridFor = (page: Page) =>
    page
      .getByRole("heading", { name: /teams/i })
      .locator("..")
      .locator("..")
      .locator(".grid.grid-cols-2.gap-3");

  await ownerPage.getByRole("button", { name: /\+ new team/i }).click();
  await expect(teamGridFor(ownerPage).locator(":scope > div")).toHaveCount(1);
  await Promise.all([
    memberAPage.waitForResponse((res) => res.url().includes("/team/join"), {
      timeout: 3000,
    }),
    teamGridFor(memberAPage)
      .locator(":scope > div")
      .nth(0)
      .getByRole("button", { name: /join/i })
      .click(),
  ]);

  await memberBPage.getByRole("button", { name: /\+ new team/i }).click();
  await expect(teamGridFor(ownerPage).locator(":scope > div")).toHaveCount(2);
  await Promise.all([
    memberCPage.waitForResponse((res) => res.url().includes("/team/join"), {
      timeout: 3000,
    }),
    teamGridFor(memberCPage)
      .locator(":scope > div")
      .nth(1)
      .getByRole("button", { name: /join/i })
      .click(),
  ]);

  await ownerPage.getByRole("button", { name: /start game/i }).click();
  await ownerPage.waitForURL(`**/game/${joinCode}`, { timeout: 15000 });

  return {
    contexts,
    joinCode,
    ownerPage,
    pages,
  };
}
