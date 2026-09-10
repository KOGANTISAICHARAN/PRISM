"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const CITIZEN_TABS = [
  { href: "/", label: "Home", icon: "◉" },
  { href: "/report", label: "Report", icon: "＋" },
  { href: "/reports", label: "My Reports", icon: "☰" },
  { href: "/profile", label: "Profile", icon: "◍" },
];

export function PrismMark({ className = "" }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 font-bold tracking-tight ${className}`}>
      <span className="grid h-7 w-7 place-items-center rounded-lg bg-prism-600 text-sm text-white">P</span>
      PRISM
    </span>
  );
}

export function TopBar({ title, back }: { title?: string; back?: string }) {
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          {back && (
            <Link href={back} className="btn-ghost px-2 py-1 text-lg" aria-label="Back">
              ←
            </Link>
          )}
          {title ? <h1 className="text-base font-semibold text-slate-900">{title}</h1> : <PrismMark />}
        </div>
        <div className="flex items-center gap-2">
          {user?.role === "inspector" && (
            <Link href="/inspector" className="hidden text-xs font-semibold text-prism-700 sm:block">
              Inspector dashboard
            </Link>
          )}
          {user ? (
            <button onClick={logout} className="btn-ghost px-3 py-1.5 text-xs">
              Sign out
            </button>
          ) : (
            <Link href="/login" className="btn-primary px-3 py-1.5 text-xs">
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();
  if (user?.role === "inspector") return null;
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden">
      <div className="mx-auto flex max-w-lg">
        {CITIZEN_TABS.map((t) => {
          const active = pathname === t.href || (t.href !== "/" && pathname.startsWith(t.href));
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium ${
                active ? "text-prism-700" : "text-slate-500"
              }`}
            >
              <span className="text-lg leading-none">{t.icon}</span>
              {t.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export function BackendStatus() {
  const [state, setState] = useState<{ ok: boolean; demo: boolean; provider: string } | null>(null);
  useEffect(() => {
    api
      .health()
      .then((h) => setState({ ok: h.status === "ok", demo: h.demo_mode, provider: h.ai_provider }))
      .catch(() => setState({ ok: false, demo: false, provider: "unavailable" }));
  }, []);
  if (!state) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
      <span className={`chip ${state.ok ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
        {state.ok ? "Backend connected" : "Backend unreachable"}
      </span>
      {state.demo && <span className="chip bg-amber-100 text-amber-800">DEMO MODE</span>}
      <span>AI provider: {state.provider}</span>
    </div>
  );
}

export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }
  }, []);
  return null;
}
