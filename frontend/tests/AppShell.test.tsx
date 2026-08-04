import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import AppShell from "../src/components/AppShell";

afterEach(() => {
  cleanup();
});

function renderShell(roles: string[] = ["style_steward"]) {
  return render(
    <MemoryRouter initialEntries={["/articles"]}>
      <AppShell
        username="prototype-user"
        roles={roles}
        logoutPending={false}
        logoutError={null}
        onLogout={vi.fn()}
      >
        <p>Workspace content</p>
      </AppShell>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  it("organizes the desktop navigation into three functional workspaces", async () => {
    const user = userEvent.setup();
    renderShell();

    const primaryNavigation = screen.getByRole("navigation", {
      name: "Primary",
    });

    expect(
      within(primaryNavigation).getByRole("link", { name: "Overview" }),
    ).toHaveAttribute("href", "/");
    expect(
      within(primaryNavigation).getByRole("link", { name: "Demo" }),
    ).toHaveAttribute("href", "/demo");
    expect(
      within(primaryNavigation).getByRole("button", { name: "Data operations" }),
    ).toBeInTheDocument();
    expect(
      within(primaryNavigation).getByRole("button", { name: "Communications" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      within(primaryNavigation).getByRole("button", { name: "Analytics" }),
    ).toBeInTheDocument();

    await user.click(
      within(primaryNavigation).getByRole("button", { name: "Data operations" }),
    );
    expect(
      within(primaryNavigation).getByRole("link", { name: /Games desk/ }),
    ).toHaveAttribute("href", "/games");
    expect(
      within(primaryNavigation).getByRole("link", { name: /Identity review/ }),
    ).toHaveAttribute("href", "/identity-queue");
    expect(
      within(primaryNavigation).getByRole("link", { name: /Historical backfills/ }),
    ).toHaveAttribute("href", "/backfills");

    await user.click(
      within(primaryNavigation).getByRole("button", { name: "Communications" }),
    );
    expect(
      within(primaryNavigation).getByRole("link", { name: /Article desk/ }),
    ).toHaveAttribute("href", "/articles");
    expect(
      within(primaryNavigation).getByRole("link", { name: /Style guides/ }),
    ).toHaveAttribute("href", "/style-guides");

    await user.click(
      within(primaryNavigation).getByRole("button", { name: "Analytics" }),
    );
    expect(
      within(primaryNavigation).getByRole("link", { name: /Season explorer/ }),
    ).toHaveAttribute("href", "/workspace");
    expect(
      within(primaryNavigation).getByRole("link", { name: /Ask the warehouse/ }),
    ).toHaveAttribute("href", "/ask");
    expect(
      within(primaryNavigation).getByRole("link", { name: /Record book/ }),
    ).toHaveAttribute("href", "/record-book");
    expect(
      within(primaryNavigation).getByRole("link", { name: /Achievement tracking/ }),
    ).toHaveAttribute("href", "/achievements");
  });

  it("keeps role-restricted communication tools out of navigation", async () => {
    const user = userEvent.setup();
    renderShell([]);

    const primaryNavigation = screen.getByRole("navigation", {
      name: "Primary",
    });
    await user.click(
      within(primaryNavigation).getByRole("button", { name: "Communications" }),
    );

    expect(
      within(primaryNavigation).getByRole("link", { name: /Article desk/ }),
    ).toBeInTheDocument();
    expect(
      within(primaryNavigation).queryByRole("link", { name: /Style guides/ }),
    ).not.toBeInTheDocument();
  });

  it("offers the same workspace structure in the compact menu", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: "Menu" }));

    const mobileNavigation = screen.getByRole("navigation", {
      name: "Primary mobile",
    });
    expect(
      within(mobileNavigation).getByRole("heading", { name: "Data operations" }),
    ).toBeInTheDocument();
    expect(
      within(mobileNavigation).getByRole("heading", { name: "Communications" }),
    ).toBeInTheDocument();
    expect(
      within(mobileNavigation).getByRole("heading", { name: "Analytics" }),
    ).toBeInTheDocument();
    expect(
      within(mobileNavigation).getByRole("link", { name: "Article desk" }),
    ).toHaveAttribute("href", "/articles");
    expect(
      within(mobileNavigation).getByRole("link", { name: "Achievement tracking" }),
    ).toHaveAttribute("href", "/achievements");
  });
});
