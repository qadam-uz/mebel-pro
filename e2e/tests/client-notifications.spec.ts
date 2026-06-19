import { expect, test } from "@playwright/test";

import {
  approveWorkshopOrder,
  loginClient,
  phoneFor,
  placeClientOrderViaApi,
  runId,
  seedOrderableBranch,
} from "./helpers";

test.setTimeout(90_000);

// CB-123 — a workshop status change emits a client notification (CB-02); the bell
// badges it, the dropdown renders a localized title + the order number, and opening
// a row navigates to the order and clears the unread count.
test("client sees a localized order notification in the bell and opens it", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const clientPhone = phoneFor(id, 60);
  const { branchId, panel, edge, ownerAccess } = await seedOrderableBranch(
    request,
    id,
  );
  const { order } = await placeClientOrderViaApi(request, {
    phone: clientPhone,
    name: `Notify Client ${id}`,
    branchId,
    panelId: panel.id,
    edgeId: edge.id,
  });

  // Workshop confirms the order → one order.confirmed notification for the client.
  await approveWorkshopOrder(request, ownerAccess, order.id, order.version);

  await loginClient(page, clientPhone, `Notify Client ${id}`);

  // The bell badges the unread notification (aria-label carries the count).
  const bell = page.getByRole("button", { name: /Bildirishnomalar - 1/ });
  await expect(bell).toBeVisible();
  await bell.click();

  // The dropdown renders the localized title and the denormalized order number,
  // never the raw event_code.
  const menu = page.getByRole("menu", { name: "Bildirishnomalar" });
  await expect(menu.getByText("Buyurtma tasdiqlandi")).toBeVisible();
  await expect(
    menu.getByText(`Buyurtma № ${order.order_number}`),
  ).toBeVisible();
  await expect(menu.getByText("order.confirmed")).toHaveCount(0);

  // Opening the row navigates to the order and marks it read (badge clears).
  await menu.getByRole("menuitem", { name: /Buyurtma tasdiqlandi/ }).click();
  await expect(page).toHaveURL(new RegExp(`/client/c/orders/${order.id}`));
  await expect(
    page.getByRole("heading", { name: order.order_number }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Bildirishnomalar - 0/ }),
  ).toBeVisible();
});
