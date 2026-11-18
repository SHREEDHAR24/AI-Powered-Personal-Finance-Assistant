"use client";

import { cn } from "@/lib/cn";

export function Button({
  children,
  className,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "soft" }) {
  const styles = {
    primary: "bg-accent text-white hover:opacity-90",
    ghost: "bg-transparent text-ink hover:bg-accent-soft",
    danger: "bg-bad text-white hover:opacity-90",
    soft: "bg-accent-soft text-accent hover:opacity-90",
  }[variant];
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        styles,
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn("rounded-2xl border border-line bg-surface p-5 shadow-[var(--shadow)]", className)}>{children}</section>;
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block text-muted">{label}</span>
      {children}
    </label>
  );
}

export const controlClass =
  "w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none ring-accent focus:ring-2";

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center" onClick={onClose}>
      <div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-2xl bg-surface p-5" onClick={(event) => event.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="text-sm text-muted" onClick={onClose} type="button">
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-line px-6 py-10 text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted">{body}</p>
    </div>
  );
}

export function Banner({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warn" }) {
  return (
    <p className={cn("rounded-xl px-3 py-2 text-sm", tone === "warn" ? "bg-amber-100 text-warn dark:bg-amber-950/40" : "bg-accent-soft text-ink")}>
      {children}
    </p>
  );
}
