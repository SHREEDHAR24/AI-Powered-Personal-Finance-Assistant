"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useUser } from "@/lib/session";
import { Button, Card, Empty } from "@/components/ui";

type Insight = {
  key: string;
  observation: string;
  data: Record<string, string | number>;
  comparison_period: string;
  explanation: string;
  action: string;
};
type Recurring = {
  id: number;
  name: string;
  status: string;
  estimated_amount: string;
  cadence: string;
  previous_dates: string[];
  next_expected_date: string | null;
};

export default function InsightsPage() {
  const user = useUser();
  const [items, setItems] = useState<Insight[]>([]);
  const [recurring, setRecurring] = useState<Recurring[]>([]);

  async function load() {
    setItems(await api<Insight[]>("/api/insights"));
    setRecurring(await api<Recurring[]>("/api/recurring"));
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Insights</h1>
        <p className="text-sm text-muted">Each note is a comparison FinMate calculated. Dismiss one if it is not useful.</p>
      </div>
      {items.length === 0 && <Empty title="No insights for this month" body="Insights appear when a category, budget, or savings rate actually moves." />}
      <div className="grid gap-3">
        {items.map((item) => (
          <Card key={item.key}>
            <p className="font-medium">{item.observation}</p>
            <p className="mt-2 text-sm">{item.explanation}</p>
            <p className="mt-1 text-sm text-muted">{item.comparison_period}</p>
            <p className="mt-2 text-sm">Suggested action: {item.action}</p>
            <Button
              className="mt-3"
              variant="ghost"
              type="button"
              onClick={async () => {
                await api("/api/insights/dismiss", { method: "POST", body: JSON.stringify({ key: item.key }) });
                await load();
              }}
            >
              Dismiss
            </Button>
          </Card>
        ))}
      </div>
      <div>
        <h2 className="text-xl font-semibold">Recurring expenses</h2>
        <p className="text-sm text-muted">Only groups with a stable amount and a weekly, monthly, or quarterly gap are listed. Confirm or reject each one.</p>
      </div>
      {recurring.length === 0 && <Empty title="No recurring charges detected" body="FinMate needs at least three similar payments before it will suggest one." />}
      {recurring.map((item) => (
        <Card key={item.id}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-medium">{item.name}</p>
              <p className="text-sm text-muted">
                {money(item.estimated_amount, user.preferred_currency)} · {item.cadence} · {item.status}
              </p>
              <p className="mt-1 text-sm">Previous dates: {item.previous_dates.join(", ")}</p>
              <p className="text-sm">{item.next_expected_date ? `Next expected ${item.next_expected_date}` : "Next date is hidden because the gap is not stable enough."}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="soft" type="button" onClick={async () => { await api(`/api/recurring/${item.id}/confirm`, { method: "POST" }); await load(); }}>Confirm</Button>
              <Button variant="ghost" type="button" onClick={async () => { await api(`/api/recurring/${item.id}/reject`, { method: "POST" }); await load(); }}>Reject</Button>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
