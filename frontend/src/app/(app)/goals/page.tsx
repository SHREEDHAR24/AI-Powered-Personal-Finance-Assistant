"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { money, percent } from "@/lib/format";
import { useUser } from "@/lib/session";
import { Button, Card, controlClass, Empty, Field } from "@/components/ui";

type Goal = {
  id: number;
  name: string;
  target_amount: string;
  current_amount: string;
  remaining_amount: string;
  target_date: string;
  progress: number | null;
  months_left: number;
  required_monthly: string | null;
  target_passed: boolean;
};

export default function GoalsPage() {
  const user = useUser();
  const [goals, setGoals] = useState<Goal[]>([]);

  async function load() {
    setGoals(await api<Goal[]>("/api/goals"));
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api("/api/goals", {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"),
        target_amount: form.get("target_amount"),
        target_date: form.get("target_date"),
      }),
    });
    event.currentTarget.reset();
    await load();
  }

  async function contribute(event: FormEvent<HTMLFormElement>, goalId: number) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api(`/api/goals/${goalId}/contributions`, {
      method: "POST",
      body: JSON.stringify({
        amount: form.get("amount"),
        contributed_on: form.get("contributed_on"),
        note: form.get("note"),
      }),
    });
    event.currentTarget.reset();
    await load();
  }

  const currency = user.preferred_currency;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Savings goals</h1>
        <p className="text-sm text-muted">Progress uses contributions you record. Forecasts are not added here.</p>
      </div>
      {goals.length === 0 && <Empty title="No goals yet" body="Add a target amount and a date. FinMate will tell you the monthly contribution that reaches it." />}
      <div className="grid gap-4">
        {goals.map((goal) => (
          <Card key={goal.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-medium">{goal.name}</h2>
                <p className="text-sm text-muted">
                  {money(goal.current_amount, currency)} saved of {money(goal.target_amount, currency)} · {money(goal.remaining_amount, currency)} left
                </p>
                <p className="mt-1 text-sm">
                  {goal.required_monthly
                    ? `About ${money(goal.required_monthly, currency)} a month until ${goal.target_date} (${goal.months_left} months).`
                    : goal.target_passed
                      ? "The target date has passed and the goal is not fully funded."
                      : "This goal is fully funded."}
                </p>
              </div>
              <button className="text-sm text-bad" type="button" onClick={async () => { await api(`/api/goals/${goal.id}`, { method: "DELETE" }); await load(); }}>
                Delete
              </button>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-line">
              <div className="h-full bg-accent" style={{ width: `${Math.min(goal.progress || 0, 100)}%` }} />
            </div>
            <p className="mt-1 text-xs text-muted">{percent(goal.progress)}</p>
            <form className="mt-4 grid gap-2 md:grid-cols-4" onSubmit={(event) => contribute(event, goal.id)}>
              <input className={controlClass} name="amount" placeholder="Amount" required />
              <input className={controlClass} type="date" name="contributed_on" required defaultValue={new Date().toISOString().slice(0, 10)} />
              <input className={controlClass} name="note" placeholder="Note" />
              <Button type="submit">Add contribution</Button>
            </form>
          </Card>
        ))}
      </div>
      <Card>
        <h2 className="mb-3 font-medium">New goal</h2>
        <form className="grid gap-3 md:grid-cols-4" onSubmit={create}>
          <Field label="Name"><input className={controlClass} name="name" required /></Field>
          <Field label="Target"><input className={controlClass} name="target_amount" required /></Field>
          <Field label="Target date"><input className={controlClass} type="date" name="target_date" required /></Field>
          <div className="flex items-end"><Button type="submit">Create goal</Button></div>
        </form>
      </Card>
    </div>
  );
}
