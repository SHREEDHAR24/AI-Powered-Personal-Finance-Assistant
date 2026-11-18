"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { money, percent, PRESETS } from "@/lib/format";
import { useUser } from "@/lib/session";
import { Banner, Card, controlClass } from "@/components/ui";

type Overview = {
  income: string;
  expenses: string;
  net_cash_flow: string;
  savings_rate: number | null;
  average_daily_spend: string;
  largest_expense: { description: string; amount: string; category: string } | null;
  highest_category: { category: string; amount: string; share: number | null } | null;
  categories: { category: string; amount: string; change_pct?: number | null }[];
  monthly: { month: string; income: string; expenses: string }[];
  patterns: { title: string; detail: string }[];
};
type Compare = {
  label: string;
  previous_label: string;
  expense_delta: string;
  expense_change_pct: number | null;
  categories: { category: string; current: string; previous: string; delta: string; change_pct: number | null }[];
};
type Anomaly = { description: string; amount: string; category: string; reason: string; score: number; times_typical: number };
type Forecast = {
  available: boolean;
  reason?: string;
  next_month_expenses?: string;
  next_month_income?: string;
  expected_savings?: string;
  note?: string;
  categories?: { category: string; amount: string }[];
  method?: string;
};

export default function AnalyticsPage() {
  const user = useUser();
  const [preset, setPreset] = useState("last_3_months");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [compare, setCompare] = useState<Compare | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const currency = user.preferred_currency;

  useEffect(() => {
    api<Overview>(`/api/analytics?preset=${preset}`).then(setOverview).catch(() => undefined);
    api<Compare>("/api/analytics/compare").then(setCompare).catch(() => undefined);
    api<{ items: Anomaly[] }>("/api/analytics/anomalies").then((data) => setAnomalies(data.items)).catch(() => undefined);
    api<Forecast>("/api/analytics/forecast").then(setForecast).catch(() => undefined);
  }, [preset]);

  const metrics = overview
    ? [
        ["Income", money(overview.income, currency)],
        ["Expenditure", money(overview.expenses, currency)],
        ["Net cash flow", money(overview.net_cash_flow, currency)],
        ["Savings rate", percent(overview.savings_rate)],
        ["Average daily spend", money(overview.average_daily_spend, currency)],
        ["Largest expense", overview.largest_expense ? `${overview.largest_expense.description} · ${money(overview.largest_expense.amount, currency)}` : "—"],
        ["Highest category", overview.highest_category ? `${overview.highest_category.category} · ${money(overview.highest_category.amount, currency)}` : "—"],
      ]
    : [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Analytics</h1>
          <p className="text-sm text-muted">Every figure is summed from your transactions.</p>
        </div>
        <select className={controlClass} value={preset} onChange={(event) => setPreset(event.target.value)}>
          {PRESETS.filter((item) => item.id !== "custom").map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {metrics.map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-muted">{label}</p>
            <p className="mt-1 text-xl font-semibold">{value}</p>
          </Card>
        ))}
      </div>
      <Card>
        <h2 className="mb-2 font-medium">Month comparison</h2>
        {compare && (
          <p className="text-sm text-muted">
            {compare.label} vs {compare.previous_label}: expenses changed by {money(compare.expense_delta, currency)}
            {compare.expense_change_pct !== null ? ` (${compare.expense_change_pct}%)` : ""}.
          </p>
        )}
        <ul className="mt-3 space-y-2 text-sm">
          {compare?.categories.slice(0, 6).map((item) => (
            <li key={item.category} className="flex justify-between gap-3 border-b border-line py-2">
              <span>{item.category}</span>
              <span>
                {money(item.current, currency)} vs {money(item.previous, currency)}
                {item.change_pct !== null ? ` · ${item.change_pct}%` : ""}
              </span>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="mb-3 font-medium">Monthly trend</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={(overview?.monthly || []).map((row) => ({ month: row.month, income: Number(row.income), expenses: Number(row.expenses) }))}>
              <XAxis dataKey="month" stroke="var(--muted)" fontSize={12} />
              <YAxis stroke="var(--muted)" fontSize={12} />
              <Tooltip />
              <Bar dataKey="income" fill="#1f7a4d" />
              <Bar dataKey="expenses" fill="#b42318" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <h2 className="font-medium">Spending forecast</h2>
        {!forecast?.available && <p className="mt-2 text-sm text-muted">{forecast?.reason || "Loading…"}</p>}
        {forecast?.available && (
          <div className="mt-2 space-y-2 text-sm">
            <Banner>{forecast.note} Method: {forecast.method}</Banner>
            <p>Estimated expenses {money(forecast.next_month_expenses, currency)}</p>
            <p>Estimated income {money(forecast.next_month_income, currency)}</p>
            <p>Estimated savings {money(forecast.expected_savings, currency)}</p>
            <ul className="mt-2 space-y-1">
              {forecast.categories?.slice(0, 6).map((item) => (
                <li key={item.category} className="flex justify-between"><span>{item.category}</span><span>{money(item.amount, currency)}</span></li>
              ))}
            </ul>
          </div>
        )}
      </Card>
      <Card>
        <h2 className="font-medium">Unusual expenses</h2>
        <p className="mt-1 text-sm text-muted">These are review flags based on your own history. They are not fraud labels.</p>
        {anomalies.length === 0 && <p className="mt-3 text-sm text-muted">Nothing unusual with the history available so far.</p>}
        <ul className="mt-3 space-y-3">
          {anomalies.map((item) => (
            <li key={`${item.description}-${item.amount}`} className="rounded-xl border border-line p-3 text-sm">
              <p className="font-medium">{item.description} · {money(item.amount, currency)}</p>
              <p className="text-muted">{item.category} · score {item.score} · {item.times_typical}× typical</p>
              <p className="mt-1">{item.reason}</p>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="mb-2 font-medium">Patterns</h2>
        {overview?.patterns.length === 0 && <p className="text-sm text-muted">Not enough repeating behaviour in the last 90 days.</p>}
        <ul className="space-y-2 text-sm">
          {overview?.patterns.map((item) => (
            <li key={item.title}><span className="font-medium">{item.title}. </span>{item.detail}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
