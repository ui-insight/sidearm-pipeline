import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it } from "vitest";
import AthleticsDemoPage from "../src/pages/AthleticsDemoPage";

afterEach(() => {
  cleanup();
});

describe("AthleticsDemoPage", () => {
  it("explains the connected workflow before the walkthrough begins", () => {
    render(
      <MemoryRouter>
        <AthleticsDemoPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", {
        name: "Follow a fact from Sidearm to the story.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Bring in the record")).toBeInTheDocument();
    expect(screen.getByText("Verify the facts")).toBeInTheDocument();
    expect(screen.getByText("Find the story")).toBeInTheDocument();
    expect(screen.getByText("Prepare the coverage")).toBeInTheDocument();
  });

  it("offers a featured walkthrough and functional starting points", () => {
    render(
      <MemoryRouter>
        <AthleticsDemoPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", { name: /Start the featured walkthrough/ }),
    ).toHaveAttribute("href", "/demo/pregame-brief");
    expect(
      screen.getByRole("link", { name: /Start walkthrough/ }),
    ).toHaveAttribute("href", "/demo/pregame-brief");
    expect(
      screen.getByRole("link", { name: /Begin with data operations/ }),
    ).toHaveAttribute("href", "/games");
    expect(
      screen.getByRole("link", { name: /Begin with analytics/ }),
    ).toHaveAttribute("href", "/workspace");
    expect(
      screen.getByRole("link", { name: /Begin with communications/ }),
    ).toHaveAttribute("href", "/articles");
  });
});
