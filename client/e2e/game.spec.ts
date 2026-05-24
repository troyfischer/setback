import { test, expect, type Browser, type Page } from "@playwright/test";
import { devLogin } from "./helpers";

async function playGame(browser: Browser, teams: string[][]) {
  const ts = Date.now();
  const allNames = teams.flat();
  const pages = new Map<string, Page>();

  for (const name of allNames) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await devLogin(page, `${name}-${ts}`);
    pages.set(name, page);
  }

  const allPages = allNames.map((n) => pages.get(n)!);
  const ownerPage = allPages[0]!;

  const teamGridFor = (page: Page) =>
    page
      .getByRole("heading", { name: /teams/i })
      .locator("..")
      .locator("..")
      .locator(".grid.grid-cols-2.gap-3");

  // --- Owner creates the game ---
  await ownerPage.getByRole("button", { name: /create game/i }).click();
  const codeEl = ownerPage.locator("p.font-mono");
  await expect(codeEl).toBeVisible();
  const joinCode = (await codeEl.textContent())!.trim();

  // --- Everyone except the owner joins via the code ---
  for (const name of allNames.slice(1)) {
    const page = pages.get(name)!;
    await page.getByPlaceholder(/abc123/i).fill(joinCode);
    await page.getByRole("button", { name: /join game/i }).click();
    await page.waitForURL(`**/lobby/${joinCode}`, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: /teams/i })).toBeVisible();
  }

  // --- First player of each team creates the team (auto-joined), rest join ---
  for (let t = 0; t < teams.length; t++) {
    const team = teams[t]!;
    const creator = pages.get(team[0]!)!;
    await creator.getByRole("button", { name: /\+ new team/i }).click();
    await expect(teamGridFor(ownerPage).locator(":scope > div")).toHaveCount(
      t + 1,
      {
        timeout: 8000,
      },
    );

    for (const member of team.slice(1)) {
      const memberPage = pages.get(member)!;
      const targetTeam = teamGridFor(memberPage).locator(":scope > div").nth(t);
      await Promise.all([
        memberPage.waitForResponse((res) => res.url().includes("/team/join"), {
          timeout: 3000,
        }),
        targetTeam.getByRole("button", { name: /join/i }).click(),
      ]);
    }
  }

  // --- Owner starts the game ---
  await ownerPage.getByRole("button", { name: /start game/i }).click();
  for (const page of allPages) {
    await page.waitForURL("**/game/**", { timeout: 15000 });
  }

  // --- Play until "Game over" ---
  async function findActivePlayer(): Promise<Page | null> {
    const results = await Promise.all(
      allPages.map((p) =>
        p
          .locator("text=Your turn")
          .isVisible()
          .catch(() => false),
      ),
    );
    const idx = results.findIndex((v) => v);
    return idx >= 0 ? allPages[idx]! : null;
  }

  // Each round needs ~(N bids + 6 tricks × N plays) = 7N actions; allow many rounds.
  const maxIterations = allPages.length * 7 * 20;
  for (let i = 0; i < maxIterations; i++) {
    if (
      await ownerPage
        .locator("text=Game over")
        .isVisible()
        .catch(() => false)
    )
      break;

    const player = await findActivePlayer();
    if (!player) {
      await ownerPage.waitForTimeout(300);
      continue;
    }

    // Play phase
    const cardLocator = player.locator(
      'button[data-testid="playing-card"]:not([disabled])',
    );
    const cardCount = await cardLocator.count();
    if (cardCount > 0) {
      for (let c = 0; c < cardCount; c++) {
        const [response] = await Promise.all([
          player.waitForResponse(
            (res) => res.url().includes("/game/trick/play"),
            { timeout: 3000 },
          ),
          cardLocator.nth(c).click(),
        ]);
        if (response.ok()) break;
        await player.waitForTimeout(200);
      }
      continue;
    }

    // Bid phase
    const bid2 = player.getByRole("button", { name: /^bid 2$/i });
    if (await bid2.isVisible().catch(() => false)) {
      const [response] = await Promise.all([
        player.waitForResponse((res) => res.url().includes("/game/bid"), {
          timeout: 3000,
        }),
        bid2.click(),
      ]);
      if (response.ok()) continue;
    }
    const pass = player.getByRole("button", { name: /^pass$/i });
    if (await pass.isVisible().catch(() => false)) {
      const [response] = await Promise.all([
        player.waitForResponse((res) => res.url().includes("/game/bid"), {
          timeout: 3000,
        }),
        pass.click(),
      ]);
      if (response.ok()) continue;
    }

    await ownerPage.waitForTimeout(300);
  }

  await expect(ownerPage.locator("text=Game over")).toBeVisible({
    timeout: 15000,
  });
}

test("2 teams of 2", async ({ browser }) => {
  test.setTimeout(300000);
  await playGame(browser, [
    ["alice", "bob"],
    ["carol", "dave"],
  ]);
});

test("3 teams of 2", async ({ browser }) => {
  test.setTimeout(300000);
  await playGame(browser, [
    ["alice", "bob"],
    ["carol", "dave"],
    ["eli", "ferdinand"],
  ]);
});

test("4 teams of 2", async ({ browser }) => {
  test.setTimeout(300000);
  await playGame(browser, [
    ["alice", "bob"],
    ["carol", "dave"],
    ["eli", "ferdinand"],
    ["gabe", "holly"],
  ]);
});
