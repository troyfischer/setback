import { test, expect, type Page } from "@playwright/test";
import {
  devLogin,
  setupInProgressGame,
  setupTwoPlayerLobby,
  type InProgressGameSetup,
  type TwoPlayerLobbySetup,
} from "./helpers";

test("guest can log in and see the lobby", async ({ page }) => {
  await devLogin(page, `test-${Date.now()}`);
  await expect(page.getByRole("heading", { name: /setback/i })).toBeVisible();
});

test.describe("lobby", () => {
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
    const { memberCtx, memberPage, ownerCtx, ownerPage } =
      await setupTwoPlayerLobby(browser);

    await expect(ownerPage.getByRole("heading", { name: /teams/i })).toBeVisible();
    await expect(memberPage.getByRole("heading", { name: /teams/i })).toBeVisible();

    await ownerCtx.close();
    await memberCtx.close();
  });
});

test.describe("rejoin", () => {
  let setup: TwoPlayerLobbySetup;

  async function expectWaitingRejoinSummary(page: Page, joinCode: string) {
    await expect(
      page.getByRole("heading", { name: /rejoin a game/i }),
    ).toBeVisible();
    await expect(page.getByText("Waiting to Start")).toBeVisible();
    await expect(
      page.getByText(new RegExp(`Join code\\s+${joinCode}`)),
    ).toBeVisible();
    await expect(page.getByText("2 players at the table")).toBeVisible();
  }

  test.beforeEach(async ({ browser }) => {
    setup = await setupTwoPlayerLobby(browser);
  });

  test.afterEach(async () => {
    await setup.ownerCtx.close();
    await setup.memberCtx.close();
  });

  test("shows summary", async () => {
    const { joinCode, memberPage, ownerPage } = setup;

    await memberPage.getByRole("button", { name: /leave table/i }).click();
    await memberPage.waitForURL("**/lobby", { timeout: 15000 });
    await expectWaitingRejoinSummary(memberPage, joinCode);

    await ownerPage.getByRole("button", { name: /leave table/i }).click();
    await ownerPage.waitForURL("**/lobby", { timeout: 15000 });
    await expectWaitingRejoinSummary(ownerPage, joinCode);
  });

  test("survives hard reload via refresh auth", async () => {
    const { joinCode, memberPage } = setup;

    await memberPage.goto("/lobby");
    await memberPage.waitForURL("**/lobby", { timeout: 15000 });
    await expectWaitingRejoinSummary(memberPage, joinCode);
  });

  async function expectInProgressRejoinCard(page: Page, joinCode: string) {
    await expect(
      page.getByRole("heading", { name: /rejoin a game/i }),
    ).toBeVisible();
    const rejoinCard = page
      .getByRole("button", { name: /rejoin/i })
      .locator("..")
      .locator("..");
    await expect(rejoinCard.getByText("In Progress")).toBeVisible();
    await expect(rejoinCard.getByText(joinCode)).toBeVisible();
    return rejoinCard;
  }

  async function expectLoadedGameScreen(page: Page, joinCode: string) {
    await page.waitForURL(`**/game/${joinCode}`, { timeout: 15000 });
    await expect(page).not.toHaveURL(`http://localhost:8081/lobby/${joinCode}`);
    await expect(page.getByText(/waiting for game state/i)).not.toBeVisible();
    await expect(page.getByText(/target/i)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /teams/i }),
    ).not.toBeVisible();
  }

  test.describe("in progress", () => {
    let inProgress: InProgressGameSetup;

    async function findActivePlayer(pages: Page[]): Promise<Page | null> {
      const results = await Promise.all(
        pages.map((page) =>
          page
            .getByText("Your turn", { exact: true })
            .isVisible()
            .catch(() => false),
        ),
      );
      const idx = results.findIndex(Boolean);
      return idx >= 0 ? pages[idx]! : null;
    }

    async function completeBidRound(pages: Page[], ownerPage: Page) {
      const maxActions = pages.length + 2;

      for (let i = 0; i < maxActions; i++) {
        if (!(await ownerPage.getByRole("button", { name: /^bid 2$/i }).isVisible().catch(() => false))) {
          break;
        }

        const activePlayer = await findActivePlayer(pages);
        if (!activePlayer) {
          await ownerPage.waitForTimeout(300);
          continue;
        }

        const [response] = await Promise.all([
          activePlayer.waitForResponse((res) => res.url().includes("/game/bid"), {
            timeout: 3000,
          }),
          activePlayer.getByRole("button", { name: /^bid 2$/i }).click(),
        ]);
        expect(response.ok()).toBeTruthy();
      }

      await expect(
        ownerPage.getByRole("button", { name: /^bid 2$/i }),
      ).toHaveCount(0);
    }

    test.beforeEach(async ({ browser }) => {
      inProgress = await setupInProgressGame(browser);
    });

    test.afterEach(async () => {
      await Promise.all(inProgress.contexts.map((ctx) => ctx.close()));
    });

    test("rejoins active game directly from lobby after reload", async () => {
      const { joinCode, ownerPage } = inProgress;

      await ownerPage.goto("/lobby");
      await ownerPage.waitForURL("**/lobby", { timeout: 15000 });
      const rejoinCard = await expectInProgressRejoinCard(ownerPage, joinCode);

      await rejoinCard.getByRole("button", { name: /rejoin/i }).click();
      await expectLoadedGameScreen(ownerPage, joinCode);
    });

    test("rejoins active game directly from lobby after leaving", async () => {
      const { joinCode, ownerPage } = inProgress;

      await ownerPage.getByRole("button", { name: /^leave$/i }).click();
      await ownerPage.waitForURL("**/lobby", { timeout: 15000 });
      const rejoinCard = await expectInProgressRejoinCard(ownerPage, joinCode);

      await rejoinCard.getByRole("button", { name: /rejoin/i }).click();
      await expectLoadedGameScreen(ownerPage, joinCode);
    });

    test("shows completed bid summary and full round details", async () => {
      const { ownerPage, pages } = inProgress;

      await completeBidRound(pages, ownerPage);

      const biddingCard = ownerPage.locator("details", {
        has: ownerPage.getByRole("heading", { name: /^bidding$/i }),
      });

      await expect(
        biddingCard.getByText(/won the bid with 2\./i),
      ).toBeVisible();
      await expect(
        biddingCard.getByRole("row", { name: /player action detail/i }),
      ).not.toBeVisible();

      await biddingCard.locator("summary").click();

      await expect(
        biddingCard.getByRole("row", { name: /player action detail/i }),
      ).toBeVisible();
      await expect(biddingCard.getByRole("row")).toHaveCount(5);
      await expect(biddingCard.getByRole("cell", { name: "Bid" })).toHaveCount(
        4,
      );
    });
  });
});
