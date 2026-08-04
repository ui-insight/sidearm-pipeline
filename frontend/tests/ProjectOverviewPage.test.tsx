import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it } from "vitest";
import ProjectOverviewPage from "../src/pages/ProjectOverviewPage";

afterEach(() => {
  cleanup();
});

describe("ProjectOverviewPage", () => {
  it("explains the project in user-facing language", () => {
    render(
      <MemoryRouter>
        <ProjectOverviewPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", {
        name: "The data foundation for every Vandal sport.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Sidearm ingestion")).toBeInTheDocument();
    expect(screen.getByText("One all-sport warehouse")).toBeInTheDocument();
    expect(screen.getByText("Athletics intelligence")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "What this platform is here to do" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Bring athletics records into one workspace"),
    ).toBeInTheDocument();
  });

  it("shows the working prototype capabilities", () => {
    render(
      <MemoryRouter>
        <ProjectOverviewPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Available in this prototype" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Season and game intake")).toBeInTheDocument();
    expect(screen.getByText("Article preparation")).toBeInTheDocument();
    expect(screen.getByText("Ready to demonstrate")).toBeInTheDocument();
  });

  it("links to the demo and games desk", () => {
    render(
      <MemoryRouter>
        <ProjectOverviewPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", { name: "Explore the Athletics demo" }),
    ).toHaveAttribute("href", "/demo");
    expect(
      screen.getByRole("link", { name: "View ingested games" }),
    ).toHaveAttribute("href", "/games");
  });
});
