"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { PrismMark } from "@/components/Shell";
import { AIDisclaimer, Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { label: "Demo citizen", email: "citizen@prism.demo", password: "demo1234", role: "citizen" },
  { label: "Demo inspector", email: "inspector@prism.demo", password: "demo1234", role: "inspector" },
];

function LoginInner() {
  const { login, register } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [form, setForm] = useState({ email: "", password: "", name: "", phone: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function go(role: string) {
    if (next) router.replace(next);
    else router.replace(role === "inspector" ? "/inspector" : "/");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user =
        mode === "login"
          ? await login(form.email.trim(), form.password)
          : await register({
              email: form.email.trim(),
              password: form.password,
              name: form.name.trim(),
              phone: form.phone || undefined,
              role: "citizen",
            });
      go(user.role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  async function demoLogin(email: string, password: string) {
    setBusy(true);
    setError(null);
    try {
      const user = await login(email, password);
      go(user.role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <Link href="/" className="mb-6 self-start text-sm text-slate-500">
        ← Back
      </Link>
      <PrismMark className="text-lg" />
      <h1 className="mt-4 text-2xl font-bold text-slate-900">
        {mode === "login" ? "Sign in to PRISM" : "Create your PRISM account"}
      </h1>
      <p className="mt-1 text-sm text-slate-600">
        Citizens report issues and track status. Inspectors review cases and record decisions.
      </p>

      <form onSubmit={submit} className="card mt-6 space-y-4">
        {mode === "signup" && (
          <div>
            <label className="label" htmlFor="name">
              Full name
            </label>
            <input
              id="name"
              className="input"
              required
              minLength={2}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
        )}
        <div>
          <label className="label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            className="input"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </div>
        <div>
          <label className="label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            className="input"
            required
            minLength={6}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </div>
        {mode === "signup" && (
          <div>
            <label className="label" htmlFor="phone">
              Phone (optional)
            </label>
            <input
              id="phone"
              inputMode="tel"
              className="input"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </div>
        )}
        {error && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button
          type="button"
          className="btn-ghost w-full py-2 text-xs"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
        >
          {mode === "login" ? "New to PRISM? Create an account" : "Already have an account? Sign in"}
        </button>
      </form>

      <div className="card mt-4">
        <p className="section-title">Demo accounts (synthetic data)</p>
        <div className="mt-3 grid gap-2">
          {DEMO_ACCOUNTS.map((a) => (
            <button
              key={a.email}
              type="button"
              className="btn-secondary justify-between py-2.5 text-xs"
              onClick={() => demoLogin(a.email, a.password)}
              disabled={busy}
            >
              <span className="font-semibold">{a.label}</span>
              <span className="font-mono text-[11px] text-slate-500">{a.email}</span>
            </button>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-slate-500">Password for both demo accounts: demo1234</p>
      </div>

      <div className="mt-4">
        <AIDisclaimer compact />
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <LoginInner />
    </Suspense>
  );
}
