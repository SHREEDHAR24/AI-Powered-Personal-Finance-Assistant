"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { money, percent } from "@/lib/format";
import { useUser } from "@/lib/session";
import { Banner, Button, Card, controlClass, Empty, Field } from "@/components/ui";

type Item = {
  id: number;
  category_id: number;
  category_name: string;
  monthly_limit: string;
  spent: string;
  remaining: string;
  utilisation: number | null;
  level: string;
};
type Status = { month: number; year: number; items: Item[]; alerts: string[]; utilisation: number | null };
type Category = { id: number; name: string; transaction_type: string };

export default function BudgetsPage() {
  const user = useUser();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [status, setStatus] = useState<Status | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setStatus(await api<Status>(`/api/budgets?month=${month}&year=${year}`));
  }

  useEffect(() => {
    api<Category[]>("/api/categories").then(setCategories).catch(() => undefined);
  }, []);

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, year]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/budgets", {
        method: "POST",
        body: JSON.stringify({
          category_id: Number(form.get("category_id")),
          monthly_limit: form.get("monthly_limit"),
          month,
          year,
        }),
      });
      event.currentTarget.reset();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the budget");
    }
  }

  async function suggest() {
    await api(`/api/budgets/suggest?month=${month}&year=${year}`, { method: "POST" });
    await load();
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Budgets</h1>
          <p className="text-sm text-muted">Overall use {percent(status?.utilisation ?? null)}</p>
        </div>
        <div className="flex gap-2">
          <input className={controlClass} type="number" value={month} min={1} max={12} onChange={(event) => setMonth(Number(event.target.value))} />
          <input className={controlClass} type="number" value={year} onChange={(event) => setYear(Number(event.target.value))} />
          <Button variant="soft" onClick={suggest} type="button">Use last month</Button>
        </div>
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
      {status?.alerts.map((alert) => <Banner key={alert} tone="warn">{alert}</Banner>)}
      {status && status.items.length === 0 && <Empty title="No budgets this month" body="Add a category limit, or copy last month's spending as a starting point." />}
      <div className="grid gap-3">
        {status?.items.map((item) => (
          <Card key={item.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium">{item.category_name}</p>
                <p className="text-sm text-muted">
                  {money(item.spent, user.preferred_currency)} of {money(item.monthly_limit, user.preferred_currency)} · {money(item.remaining, user.preferred_currency)} left
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm">{percent(item.utilisation)}</span>
                <form
                  className="flex items-center gap-2"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    const limit = new FormData(event.currentTarget).get("monthly_limit");
                    await api(`/api/budgets/${item.id}`, { method: "PATCH", body: JSON.stringify({ monthly_limit: limit }) });
                    await load();
                  }}
                >
                  <input className={`${controlClass} w-28`} name="monthly_limit" defaultValue={item.monthly_limit} />
                  <button className="text-sm text-accent" type="submit">Update</button>
                </form>
                <button
                  className="text-sm text-bad"
                  type="button"
                  onClick={async () => {
                    await api(`/api/budgets/${item.id}`, { method: "DELETE" });
                    await load();
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-line">
              <div
                className={`h-full ${item.level === "over" ? "bg-bad" : item.level === "ok" ? "bg-accent" : "bg-warn"}`}
                style={{ width: `${Math.min(item.utilisation || 0, 100)}%` }}
              />
            </div>
          </Card>
        ))}
      </div>
      <Card>
        <h2 className="mb-3 font-medium">New budget</h2>
        <form className="grid gap-3 md:grid-cols-3" onSubmit={create}>
          <Field label="Category">
            <select className={controlClass} name="category_id" required>
              {categories.filter((category) => category.transaction_type === "expense").map((category) => (
                <option key={category.id} value={category.id}>{category.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Monthly limit">
            <input className={controlClass} name="monthly_limit" required />
          </Field>
          <div className="flex items-end"><Button type="submit">Save budget</Button></div>
        </form>
      </Card>
    </div>
  );
}
