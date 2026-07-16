import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authApi } from "../src/api/auth";
import AuthenticationBoundary from "../src/components/AuthenticationBoundary";

vi.mock("../src/api/auth", () => ({
  authApi: {
    session: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

const sessionMock = vi.mocked(authApi.session);
const loginMock = vi.mocked(authApi.login);
const logoutMock = vi.mocked(authApi.logout);

function renderBoundary() {
  return render(
    <AuthenticationBoundary>
      {({ username, onLogout, logoutPending }) => (
        <div>
          <p>Welcome, {username}</p>
          <button type="button" onClick={() => void onLogout()}>
            {logoutPending ? "Signing out" : "Sign out"}
          </button>
        </div>
      )}
    </AuthenticationBoundary>,
  );
}

describe("AuthenticationBoundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows the login screen when no session exists", async () => {
    sessionMock.mockResolvedValue({ authenticated: false, username: null });

    renderBoundary();

    expect(screen.getByRole("status")).toHaveTextContent("Checking access");
    expect(
      await screen.findByRole("heading", { name: "Sign in to the stats desk" }),
    ).toBeInTheDocument();
  });

  it("keeps invalid credential feedback beside the form", async () => {
    const user = userEvent.setup();
    sessionMock.mockResolvedValue({ authenticated: false, username: null });
    loginMock.mockRejectedValue(new Error("Username or password is incorrect"));
    renderBoundary();

    await user.type(await screen.findByLabelText("Username"), "prototype-user");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Username or password is incorrect",
    );
  });

  it("opens the authenticated workspace after login", async () => {
    const user = userEvent.setup();
    sessionMock.mockResolvedValue({ authenticated: false, username: null });
    loginMock.mockResolvedValue({
      authenticated: true,
      username: "prototype-user",
    });
    renderBoundary();

    await user.type(await screen.findByLabelText("Username"), "prototype-user");
    await user.type(screen.getByLabelText("Password"), "prototype-pass");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Welcome, prototype-user")).toBeInTheDocument();
  });

  it("returns to login after logout", async () => {
    const user = userEvent.setup();
    sessionMock.mockResolvedValue({
      authenticated: true,
      username: "prototype-user",
    });
    logoutMock.mockResolvedValue({ authenticated: false, username: null });
    renderBoundary();

    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(
      await screen.findByRole("heading", { name: "Sign in to the stats desk" }),
    ).toBeInTheDocument();
  });
});
