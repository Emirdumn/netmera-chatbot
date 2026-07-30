import type { ReactElement } from "react";
import { strings } from "../strings";
import type { TabId } from "../types";
import styles from "./TabBar.module.css";

export interface TabBarProps {
  active: TabId;
  unreadCount?: number;
  onChange: (tab: TabId) => void;
}

const TABS: { id: TabId; label: string; Icon: () => ReactElement }[] = [
  { id: "home", label: strings.tabs.home, Icon: HomeIcon },
  { id: "messages", label: strings.tabs.messages, Icon: MessageIcon },
  { id: "help", label: strings.tabs.help, Icon: HelpIcon },
];

export function TabBar({ active, unreadCount = 0, onChange }: TabBarProps) {
  return (
    <nav className={styles.tabBar} role="tablist" aria-label={strings.panel.ariaLabel}>
      {TABS.map(({ id, label, Icon }) => {
        const isActive = id === active;
        const showBadge = id === "messages" && unreadCount > 0;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            id={`nm-tab-${id}`}
            aria-selected={isActive}
            aria-controls={`nm-panel-${id}`}
            tabIndex={isActive ? 0 : -1}
            className={`${styles.tab} ${isActive ? styles.active : ""}`}
            onClick={() => onChange(id)}
          >
            <span className={styles.iconWrap}>
              <Icon />
              {showBadge && (
                <span className={styles.badge} aria-hidden="true">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </span>
            <span>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function HomeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4v-5H9v5H5a1 1 0 0 1-1-1v-8.5Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function MessageIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5v8a1.5 1.5 0 0 1-1.5 1.5H9l-4 3v-3h-.5A1.5 1.5 0 0 1 4 14.5v-8Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function HelpIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="8.2" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M9.8 9.6a2.3 2.3 0 1 1 3.1 2.15c-.6.24-.9.78-.9 1.4v.35"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="12" cy="16.4" r="1" fill="currentColor" />
    </svg>
  );
}
