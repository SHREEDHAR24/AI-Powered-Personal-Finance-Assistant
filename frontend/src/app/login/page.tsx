"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button, controlClass, Field } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="text-3xl font-semibold">Sign in</h1>
      <p className="mt-2 text-sm text-muted">Your records stay on this account only.</p>
      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <Field label="Email">
          <input className={controlClass} name="email" type="email" required />
        </Field>
        <Field label="Password">
          <input className={controlClass} name="password" type="password" required minLength={8} />
        </Field>
        {error && <p className="text-sm text-bad">{error}</p>}
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        New here? <Link href="/register" className="text-accent">Create an account</Link>
      </p>
    </main>
  );
}
