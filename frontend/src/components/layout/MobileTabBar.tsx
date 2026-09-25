import { NavLink } from "react-router-dom";
import { LayoutDashboard, LineChart, MessageCircle, Puzzle, Swords } from "lucide-react";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Home", icon: LayoutDashboard, end: true },
  { to: "/sparring", label: "Spar", icon: Swords, end: false },
  { to: "/puzzles", label: "Puzzles", icon: Puzzle, end: false },
  { to: "/stats", label: "Insights", icon: LineChart, end: false },
  { to: "/coach", label: "Coach", icon: MessageCircle, end: false },
];

/** Fixed bottom tab bar, phone-first navigation for Tailscale access. */
export function MobileTabBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-stretch border-t border-slate-border bg-slate-surface/95 backdrop-blur md:hidden">
      {LINKS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium",
              isActive ? "text-amber" : "text-ink-muted",
            )
          }
        >
          <Icon className="size-5" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
