import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";

/** Mobile-only header: branding + sign out. MobileTabBar (bottom) covers
 * nav on phones, but had nowhere to put logout — this fills that gap. */
export function MobileTopBar() {
  const { logout, username } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-slate-border bg-obsidian/95 px-4 backdrop-blur md:hidden">
      <span className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-ink">
        <span className="text-amber">♞</span> Chess Coach
      </span>
      <div className="flex items-center gap-2">
        <span className="max-w-[8rem] truncate text-xs text-ink-muted">{username}</span>
        <button
          onClick={logout}
          aria-label="Log out"
          className="flex size-8 items-center justify-center rounded-md text-ink-muted transition-colors hover:bg-slate-surface hover:text-ink active:bg-slate-surface"
        >
          <LogOut className="size-4" />
        </button>
      </div>
    </header>
  );
}
