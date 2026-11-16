import { Library, MessagesSquare, PanelLeftClose, PanelLeftOpen, Plus, Scale, X } from "lucide-react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n/context";
import type { ThemeChoice } from "../state/theme";
import { SettingsPanel } from "./SettingsPanel";
import { StatusBar } from "./StatusBar";
import type { HealthState } from "./StatusBar";

export type View = "workspace" | "library";

interface Props {
  view: View;
  onNavigate: (view: View) => void;
  onNewQuery: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  /** phones and tablets: the sidebar is a drawer */
  drawerOpen: boolean;
  onCloseDrawer: () => void;
  health: HealthState;
  theme: ThemeChoice;
  onThemeChange: (theme: ThemeChoice) => void;
  /** the query history */
  children: ReactNode;
}

export function Sidebar(props: Props) {
  const { view, onNavigate, onNewQuery, collapsed, onToggleCollapsed, drawerOpen, onCloseDrawer,
          health, theme, onThemeChange, children } = props;
  const { t } = useI18n();
  const cls = ["sidebar", collapsed ? "is-collapsed" : "", drawerOpen ? "is-open" : ""]
    .filter(Boolean).join(" ");
  const nav: { id: View; label: string; icon: ReactNode }[] = [
    { id: "workspace", label: t("nav.workspace"), icon: <MessagesSquare size={18} aria-hidden="true" /> },
    { id: "library", label: t("nav.library"), icon: <Library size={18} aria-hidden="true" /> },
  ];

  return (
    <aside className={cls} aria-label="DocuMind UZ">
      <div className="sidebar__brand">
        <span className="logo" aria-hidden="true"><Scale size={18} /></span>
        <div className="sidebar__brand-text">
          <h1 className="brand__name">DocuMind UZ</h1>
          <p className="brand__tagline">{t("app.product")}</p>
        </div>
        <button type="button" className="icon-btn sidebar__close" aria-label={t("nav.close")}
                onClick={onCloseDrawer}>
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <button type="button" className="btn btn--primary sidebar__new" onClick={onNewQuery}
              aria-label={collapsed ? t("nav.newQuery") : undefined}
              title={collapsed ? t("nav.newQuery") : undefined}>
        <Plus size={18} aria-hidden="true" />
        <span className="sidebar__label">{t("nav.newQuery")}</span>
      </button>

      <nav className="sidebar__nav" aria-label={t("nav.label")}>
        {nav.map((item) => (
          <button key={item.id} type="button"
                  className={item.id === view ? "nav-item is-active" : "nav-item"}
                  aria-current={item.id === view ? "page" : undefined}
                  aria-label={collapsed ? item.label : undefined}
                  title={collapsed ? item.label : undefined}
                  onClick={() => onNavigate(item.id)}>
            {item.icon}
            <span className="sidebar__label">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar__scroll">{!collapsed && children}</div>

      <div className="sidebar__foot">
        {!collapsed && <SettingsPanel theme={theme} onThemeChange={onThemeChange} />}
        <div className="sidebar__foot-row">
          <StatusBar status={health} compact={collapsed} />
          <button type="button" className="icon-btn sidebar__collapse"
                  aria-label={collapsed ? t("nav.expand") : t("nav.collapse")}
                  title={collapsed ? t("nav.expand") : t("nav.collapse")}
                  aria-expanded={!collapsed} onClick={onToggleCollapsed}>
            {collapsed ? <PanelLeftOpen size={18} aria-hidden="true" />
                       : <PanelLeftClose size={18} aria-hidden="true" />}
          </button>
        </div>
      </div>
    </aside>
  );
}
