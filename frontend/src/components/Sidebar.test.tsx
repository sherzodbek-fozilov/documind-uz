import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { Lang } from "../i18n/messages";
import { renderIn } from "../test/render";
import { Sidebar } from "./Sidebar";

function setup(over: Partial<Parameters<typeof Sidebar>[0]> = {}, lang: Lang = "en") {
  const props = {
    view: "workspace" as const, onNavigate: vi.fn(), onNewQuery: vi.fn(), collapsed: false,
    onToggleCollapsed: vi.fn(), drawerOpen: false, onCloseDrawer: vi.fn(), theme: "dark" as const,
    onThemeChange: vi.fn(), ...over,
  };
  const result = renderIn(<Sidebar {...props}><section aria-label="History" /></Sidebar>, lang);
  return { props, ...result };
}

/** the sidebar with its own collapsed state, as in the app */
function Stateful() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <Sidebar view="workspace" onNavigate={() => {}} onNewQuery={() => {}} collapsed={collapsed}
             onToggleCollapsed={() => setCollapsed(!collapsed)} drawerOpen={false}
             onCloseDrawer={() => {}} theme="dark" onThemeChange={() => {}}>
      <section aria-label="History" />
    </Sidebar>
  );
}

/** the buttons of the sidebar, in order, by accessible name */
function buttonNames() {
  return within(screen.getByRole("complementary")).getAllByRole("button")
    .map((b) => b.getAttribute("aria-label") ?? b.textContent);
}

describe("Sidebar", () => {
  it("has [logo] [name] [collapse] in the expanded header, and no toggle at the bottom", () => {
    setup();
    const header = document.querySelector(".sidebar__brand")!;
    expect([...header.children].map((el) => el.className.split(" ")[0]))
      .toEqual(["logo", "sidebar__brand-text", "icon-btn", "icon-btn"]);
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle.previousElementSibling?.classList.contains("sidebar__brand-text")).toBe(true);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(toggle.dataset.tip).toBe("Collapse sidebar");
    expect(screen.getAllByRole("button", { name: /sidebar/ })).toHaveLength(1);
    expect(document.querySelector(".sidebar__foot")!.querySelector("button[aria-label$='sidebar']")).toBeNull();
    // the expanded sidebar has everything: brand, actions, history and settings
    expect(screen.getByRole("heading", { name: "DocuMind UZ" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "History" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Interface language" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Theme" })).toBeTruthy();
  });

  it("collapses to an icon rail whose top slot is the logo, named as the expand action", async () => {
    const { props } = setup({ collapsed: true });
    expect(screen.getByRole("complementary").classList.contains("is-collapsed")).toBe(true);
    expect(buttonNames()).toEqual(["Open sidebar", "New query", "Workspace", "Document library"]);

    const top = screen.getByRole("button", { name: "Open sidebar" });
    // shows the logo; the expand icon is swapped in by the stylesheet on hover / focus
    expect(top.querySelector(".logo.rail-logo__brand svg")).toBeTruthy();
    expect(top.querySelector(".rail-logo__expand svg")).toBeTruthy();
    expect(top.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("heading", { name: "DocuMind UZ" })).toBeNull();
    for (const name of ["Open sidebar", "New query", "Workspace", "Document library"]) {
      expect(screen.getByRole("button", { name }).dataset.tip).toBe(name);
    }
    expect(screen.queryByRole("region", { name: "History" })).toBeNull();
    expect(screen.queryByRole("group", { name: "Theme" })).toBeNull();

    await userEvent.hover(top); // hovering never expands on its own
    expect(props.onToggleCollapsed).not.toHaveBeenCalled();
    await userEvent.click(top);
    expect(props.onToggleCollapsed).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "Document library" }));
    expect(props.onNavigate).toHaveBeenCalledWith("library");
    await userEvent.click(screen.getByRole("button", { name: "New query" }));
    expect(props.onNewQuery).toHaveBeenCalledOnce();
  });

  it("works from the keyboard: Enter and Space on the rail buttons", async () => {
    const { props } = setup({ collapsed: true });
    screen.getByRole("button", { name: "Open sidebar" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(props.onToggleCollapsed).toHaveBeenCalledTimes(1);
    await userEvent.keyboard(" ");
    expect(props.onToggleCollapsed).toHaveBeenCalledTimes(2);
    await userEvent.tab();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "New query" }));
    await userEvent.tab();
    await userEvent.tab();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Document library" }));
    await userEvent.keyboard(" ");
    expect(props.onNavigate).toHaveBeenCalledWith("library");
  });

  it("keeps the keyboard focus on the toggle when it collapses and expands", async () => {
    renderIn(<Stateful />);
    screen.getByRole("button", { name: "Collapse sidebar" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open sidebar" }));
    await userEvent.keyboard("{Enter}");
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Collapse sidebar" }));
  });

  it("marks the current view in the rail", () => {
    setup({ collapsed: true, view: "library" });
    expect(screen.getByRole("button", { name: "Document library" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "Workspace" }).getAttribute("aria-current")).toBeNull();
  });

  it.each([
    ["ru", "Открыть боковую панель", "Свернуть боковую панель"],
    ["uz", "Yon panelni ochish", "Yon panelni yigʻish"],
  ] as const)("names the toggle in %s", (lang, open, close) => {
    const { rerender, props } = setup({ collapsed: true }, lang);
    expect(screen.getByRole("button", { name: open }).dataset.tip).toBe(open);
    rerender(<Sidebar {...props} collapsed={false}><section aria-label="History" /></Sidebar>);
    expect(screen.getByRole("button", { name: close }).dataset.tip).toBe(close);
  });

  it("shows the full sidebar in the phone drawer even when collapsed on desktop", async () => {
    const { props } = setup({ collapsed: true, drawerOpen: true });
    const aside = screen.getByRole("complementary");
    expect(aside.classList.contains("is-collapsed")).toBe(false);
    expect(aside.classList.contains("is-open")).toBe(true);
    expect(screen.getByRole("region", { name: "History" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Close menu" }));
    expect(props.onCloseDrawer).toHaveBeenCalledOnce();
  });
});
