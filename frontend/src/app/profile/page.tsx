"use client";

import Link from "next/link";

import { TopBar } from "@/components/Shell";
import { Field, Spinner } from "@/components/ui";
import { useAuth, useRequireAuth } from "@/lib/auth";

export default function ProfilePage() {
  const { loading: authLoading } = useRequireAuth("citizen");
  const { user, logout } = useAuth();

  if (authLoading || !user) {
    return (
      <main className="min-h-screen bg-slate-50">
        <TopBar title="Profile" back="/" />
        <div className="py-12">
          <Spinner label="Loading account details…" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 pb-20">
      <TopBar title="My Account" back="/" />

      <div className="mx-auto max-w-xl px-4 py-6 space-y-4">
        {/* User Card */}
        <div className="card space-y-4">
          <div className="flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-full bg-prism-600 text-lg font-bold text-white uppercase">
              {user.name.charAt(0)}
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">{user.name}</h1>
              <p className="text-xs text-slate-500">{user.email}</p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
            <Field label="Role" value={<span className="chip bg-prism-100 text-prism-800 font-semibold uppercase">Citizen Reporter</span>} />
            <Field label="User ID" value={<span className="font-mono text-xs">{user.id}</span>} />
          </div>
        </div>

        {/* Quick Links */}
        <div className="card space-y-2">
          <h2 className="text-sm font-bold text-slate-900">Quick Links</h2>
          <Link href="/reports" className="btn-secondary w-full justify-between py-2.5 text-xs">
            <span>☰ View My Reports & Status</span>
            <span>→</span>
          </Link>
          <Link href="/report" className="btn-secondary w-full justify-between py-2.5 text-xs">
            <span>＋ Report a Food Safety Issue</span>
            <span>→</span>
          </Link>
        </div>

        {/* Session Management */}
        <div className="card space-y-3">
          <h2 className="text-sm font-bold text-slate-900">Session</h2>
          <p className="text-xs text-slate-500">
            Sign out of your PRISM account on this device. You will need your password to log back in.
          </p>
          <button type="button" onClick={logout} className="btn-secondary w-full border-rose-200 text-rose-700 hover:bg-rose-50 py-2.5 text-xs">
            Sign out of PRISM
          </button>
        </div>
      </div>
    </main>
  );
}
