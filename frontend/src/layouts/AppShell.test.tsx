import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../App";

describe("AppShell", () => {
  it("renders the app structure with the planned main navigation", () => {
    render(<App />);

    expect(screen.getByRole("navigation", { name: "Hauptnavigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Patienten" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Heimtag" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByLabelText("Darstellung")).toBeInTheDocument();
  });
});
