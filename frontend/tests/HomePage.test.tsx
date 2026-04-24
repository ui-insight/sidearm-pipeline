import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import HomePage from "../src/pages/HomePage";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
});

describe("HomePage", () => {
  it("renders the pipeline heading and empty state", async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Vandals Stats Pipeline" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/No games yet/i),
    ).toBeInTheDocument();
  });
});
