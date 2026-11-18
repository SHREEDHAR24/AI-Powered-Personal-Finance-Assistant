"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeftRight,
  FileText,
  LayoutDashboard,
  LineChart,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  PieChart,
  Settings,
  Sparkles,
  Sun,
  Target,
  Upload,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { User } from "@/lib/format";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/budgets", label: "Budgets", icon: PieChart },
  { href: "/goals", label: "Goals", icon: Target },
  { href: "/analytics", label: "Analytics", icon: LineChart },
  { href: "/insights", label: "Insights", icon: Sparkles },
  { href: "/assistant", label: "Assistant", icon: MessageSquare },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Shell({ user, children }: { user: User; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  async function signOut() {
    await api("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  const nav = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-4 py-5">
        <div className="grid h-10 w-10 place-items-center rounded-2xl bg-accent font-semibold text-white">Fm</div>
        <div>
          <p className="text-base font-semibold tracking-tight">FinMate</p>
          <p className="text-xs text-muted">Personal finance</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-sm",
                active ? "bg-accent-soft font-medium text-accent" : "text-ink hover:bg-accent-soft/60",
              )}
            >
              <Icon size={16} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="space-y-2 border-t border-line p-3">
        <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm" onClick={toggleTheme} type="button">
          {dark ? <Sun size={16} /> : <Moon size={16} />}
          {dark ? "Light theme" : "Dark theme"}
        </button>
        <div className="px-3 text-sm">
          <p className="font-medium">{user.name}</p>
          <p className="truncate text-xs text-muted">{user.email}</p>
        </div>
        <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-bad" onClick={signOut} type="button">
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-line bg-surface md:block">{nav}</aside>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} aria-label="Close menu" />
          <aside className="relative h-full w-72 bg-surface">{nav}</aside>
        </div>
      )}
      <div className="md:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-canvas/90 px-4 py-3 backdrop-blur md:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open menu" type="button">
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="font-semibold">FinMate</span>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
