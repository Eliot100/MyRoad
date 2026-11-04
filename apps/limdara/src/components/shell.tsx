import { Link, useRouterState } from "@tanstack/react-router";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { BRAND, BRAND_HE } from "@/lib/brand";
import { useHydrated } from "@/lib/progress";

const THEME_KEY = "limdara-theme";

function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
  }, []);

  function flip() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem(THEME_KEY, next);
    setTheme(next);
  }

  const Icon = theme === "dark" ? Sun : Moon;
  return (
    <button
      type="button"
      onClick={flip}
      aria-label="Switch color theme"
      className="inline-flex size-11 items-center justify-center text-ink"
    >
      <Icon className="size-5" aria-hidden="true" />
    </button>
  );
}

const TABS = [
  { to: "/", label: "Roads", exact: true },
  { to: "/review", label: "Review", exact: false },
  { to: "/progress", label: "Progress", exact: false },
  { to: "/android", label: "Android", exact: false },
] as const;

function NavLinks({ dock }: { dock?: boolean }) {
  const path = useRouterState({ select: (state) => state.location.pathname });
  return (
    <>
      {TABS.map((tab) => {
        const on = tab.exact ? path === tab.to : path === tab.to || path.startsWith(`${tab.to}/`);
        const className = dock
          ? `flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-xs ${on ? "text-pine" : "text-ink"}`
          : `inline-flex min-h-11 items-center px-2 ${on ? "text-pine" : "text-ink"}`;
        return (
          <Link key={tab.to} to={tab.to} className={className} aria-current={on ? "page" : undefined}>
            {tab.label}
          </Link>
        );
      })}
    </>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  useHydrated();
  return (
    <div className="min-h-screen bg-paper text-ink">
      <a href="#content" className="skip">
        Skip to content
      </a>
      <header className="safe-top border-b border-line bg-paper">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 px-4">
          <Link to="/" className="flex min-h-11 items-baseline gap-2 py-3 text-ink">
            <span className="font-display text-2xl tracking-tight">{BRAND}</span>
            <span lang="he" dir="rtl" className="text-sm text-stone">
              {BRAND_HE}
            </span>
          </Link>
          <div className="flex items-center gap-1 text-sm">
            <div className="hidden items-center sm:flex">
              <NavLinks />
              <Link to="/forge" className="inline-flex min-h-11 items-center px-2 text-ink">
                Forge
              </Link>
            </div>
            <Link to="/forge" className="inline-flex min-h-11 items-center px-2 text-ink sm:hidden">
              Forge
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <div id="content" className="pb-24 sm:pb-0">
        {children}
      </div>
      <footer className="mx-auto max-w-5xl px-4 py-10 text-sm text-stone">
        <p>
          {BRAND} is the learning-roads platform. Progress stays on this device.{" "}
          <Link to="/name" className="text-pine">
            The name
          </Link>
          .
        </p>
      </footer>
      <nav className="dock safe-bottom sm:hidden" aria-label="App">
        <div className="mx-auto flex max-w-lg">
          <NavLinks dock />
        </div>
      </nav>
    </div>
  );
}
