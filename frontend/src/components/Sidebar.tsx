import { Library, MessagesSquare, PanelLeftClose, PanelLeftOpen, Plus, Scale, X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n/context";
import type { ThemeChoice } from "../state/theme";
import { SettingsPanel } from "./SettingsPanel";

export type View = "workspace" | "library";

interface Props {
  view: View;
  onNavigate: (view: View) => void;
  onNewQuery: () => void;
  /** desktop: the sidebar is reduced to an icon rail */
  collapsed: boolean;
  onToggleCollapsed: () => void;
  /** phones and tablets: the sidebar is a drawer */
  drawerOpen: boolean;
  onCloseDrawer: () => void;
  theme: ThemeChoice;
  onThemeChange: (theme: ThemeChoice) => void;
  /** the query history */
  children: ReactNode;
}

/**
 * Navigation. On desktop it is either expanded or a narrow icon rail; on phones and
 * tablets it is a drawer, always shown expanded.
 *
 * - Expanded header: [logo] [name + tagline] [collapse button].
 * - Rail: the top slot is the expand button. It shows the logo, and the expand icon on
 *   hover or keyboard focus; its name is always the action ("Open sidebar").
 *
 * Icon-only buttons have an aria-label; `data-tip` draws the same text as a tooltip on
 * hover and keyboard focus (see .has-tip in the stylesheet).
 */
export function Sidebar(props: Props) {
  const { view, onNavigate, onNewQuery, collapsed, onToggleCollapsed, drawerOpen, onCloseDrawer,
          theme, onThemeChange, children } = props;
  const { t } = useI18n();
  // the drawer always shows everything, whatever the desktop choice
  const rail = collapsed && !drawerOpen;
  const cls = ["sidebar", rail ? "is-collapsed" : "", drawerOpen ? "is-open" : ""]
    .filter(Boolean).join(" ");
  const nav: { id: View; label: string; icon: ReactNode }[] = [
    { id: "workspace", label: t("nav.workspace"), icon: <MessagesSquare size={18} aria-hidden="true" /> },
    { id: "library", label: t("nav.library"), icon: <Library size={18} aria-hidden="true" /> },
  ];
  /** tooltip and accessible name, only where the button shows no text */
  const tip = (label: string) => (rail ? { "aria-label": label, "data-tip": label } : {});

  // The toggle is a different button in each state (it moves from the header's right
  // end to the rail's top slot): keep the keyboard focus on it across the switch.
  const toggle = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (!refocus.current) return;
    refocus.current = false;
    toggle.current?.focus();
  }, [rail]);
  function onToggle() {
    refocus.current = toggle.current !== null && document.activeElement === toggle.current;
    onToggleCollapsed();
  }

  return (
    <aside className={cls} aria-label="DocuMind UZ">
      <div className="sidebar__brand">
        {rail ? (
          <button type="button" ref={toggle} className="sidebar__collapse rail-logo has-tip"
                  aria-label={t("nav.expand")} data-tip={t("nav.expand")} aria-expanded={false}
                  onClick={onToggle}>
            <span className="logo rail-logo__brand" aria-hidden="true"><Scale size={18} /></span>
            <span className="rail-logo__expand" aria-hidden="true"><PanelLeftOpen size={18} /></span>
          </button>
        ) : (
          <>
            <span className="logo" aria-hidden="true"><Scale size={18} /></span>
            <div className="sidebar__brand-text">
              <h1 className="brand__name">DocuMind UZ</h1>
              <p className="brand__tagline">{t("app.product")}</p>
            </div>
            <button type="button" ref={toggle} className="icon-btn sidebar__collapse has-tip"
                    aria-label={t("nav.collapse")} data-tip={t("nav.collapse")} aria-expanded={true}
                    onClick={onToggle}>
              <PanelLeftClose size={18} aria-hidden="true" />
            </button>
            <button type="button" className="icon-btn sidebar__close" aria-label={t("nav.close")}
                    onClick={onCloseDrawer}>
              <X size={18} aria-hidden="true" />
            </button>
          </>
        )}
      </div>

      <button type="button" className="btn btn--primary sidebar__new has-tip" onClick={onNewQuery}
              {...tip(t("nav.newQuery"))}>
        <Plus size={18} aria-hidden="true" />
        <span className="sidebar__label">{t("nav.newQuery")}</span>
      </button>

      <nav className="sidebar__nav" aria-label={t("nav.label")}>
        {nav.map((item) => (
          <button key={item.id} type="button"
                  className={item.id === view ? "nav-item has-tip is-active" : "nav-item has-tip"}
                  aria-current={item.id === view ? "page" : undefined}
                  {...tip(item.label)}
                  onClick={() => onNavigate(item.id)}>
            {item.icon}
            <span className="sidebar__label">{item.label}</span>
          </button>
        ))}
      </nav>

      {!rail && (
        <>
          <div className="sidebar__scroll">{children}</div>
          <div className="sidebar__foot">
            <SettingsPanel theme={theme} onThemeChange={onThemeChange} />
          </div>
        </>
      )}
    </aside>
  );
}
