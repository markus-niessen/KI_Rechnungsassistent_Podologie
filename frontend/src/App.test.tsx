import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the frontend workspace", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("opens and closes the navigation drawer from the header", () => {
    render(<App />);

    const menuButton = screen.getByRole("button", { name: "Navigation öffnen" });
    fireEvent.click(menuButton);

    expect(menuButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Navigation durch Klick außerhalb schließen" })).toBeInTheDocument();

    fireEvent.click(menuButton);

    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Navigation durch Klick außerhalb schließen" })).not.toBeInTheDocument();
  });

  it("closes the navigation drawer with the overlay and Escape", () => {
    render(<App />);

    const menuButton = screen.getByRole("button", { name: "Navigation öffnen" });
    fireEvent.click(menuButton);
    fireEvent.click(screen.getByRole("button", { name: "Navigation durch Klick außerhalb schließen" }));
    expect(menuButton).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(menuButton);
    fireEvent.keyDown(document, { key: "Escape" });

    expect(menuButton).toHaveAttribute("aria-expanded", "false");
  });
});
