import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16">
      <p className="text-sm font-medium tracking-wide text-accent">FinMate</p>
      <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight md:text-6xl">See where your money actually goes.</h1>
      <p className="mt-5 max-w-xl text-lg text-muted">
        Track income and expenses, import a bank CSV, watch budgets, and ask questions that are answered from your records. Forecasts stay labelled as estimates.
      </p>
      <div className="mt-8 flex gap-3">
        <Link href="/register" className="rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white">
          Create account
        </Link>
        <Link href="/login" className="rounded-xl border border-line px-4 py-2.5 text-sm font-medium">
          Sign in
        </Link>
      </div>
    </main>
  );
}
