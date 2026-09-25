import { NavLink } from "react-router-dom";
import { LayoutDashboard, LineChart, MessageCircle, Puzzle, Swords, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/sparring", label: "Sparring", icon: Swords, end: false },
  { to: "/puzzles", label: "Puzzles", icon: Puzzle, end: false },
  { to: "/stats", label: "Insights", icon: LineChart, end: false },
  { to: "/coach", label: "Coach", icon: MessageCircle, end: false },
];

export function NavBar() {
  const { logout, username } = useAuth();

  return (
    <header className="sticky top-0 z-30 hidden border-b border-slate-border bg-obsidian/95 backdrop-blur md:block">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <span className="text-sm font-semibold tracking-tight text-ink">
            <span className="text-amber">♞</span> Chess Coach
          </span>
          <nav className="flex items-center gap-1">
            {LINKS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-slate-surface-raised text-amber"
                      : "text-ink-muted hover:bg-slate-surface hover:text-ink",
                  )
                }
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-ink-muted">{username}</span>
          <button
            onClick={logout}
            title="Log out"
            className="flex size-8 items-center justify-center rounded-md text-ink-muted transition-colors hover:bg-slate-surface hover:text-ink"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
