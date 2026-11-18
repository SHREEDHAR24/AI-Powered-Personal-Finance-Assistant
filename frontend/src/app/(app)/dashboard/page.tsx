"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { CHART_COLORS, money, percent, PRESETS } from "@/lib/format";
import { useUser } from "@/lib/session";
import { Banner, Card, controlClass, Empty } from "@/components/ui";

type Dashboard = {
  start: string;
  end: string;
  summary: {
    income: string;
    expenses: string;
    balance: string;
    savings: string;
    savings_rate: number | null;
    transaction_count: number;
  };
  budget_utilisation: number | null;
  budget_alerts: string[];
  income_expense: { month: string; income: string; expenses: string; savings: string }[];
  categories: { category: string; amount: string }[];
  weekly: { week: string; amount: string }[];
  top_categories: { category: string; amount: string }[];
  recent: { id: number; date: string; description: string; amount: string; type: string; category_name: string }[];
};

export default function DashboardPage() {
  const user = useUser();
  const [preset, setPreset] = useState("this_month");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ preset });
    if (preset === "custom" && start && end) {
      params.set("start", start);
      params.set("end", end);
    }
    if (preset === "custom" && (!start || !end)) return;
    api<Dashboard>(`/api/dashboard?${params}`)
      .then((payload) => {
        setData(payload);
        setError("");
      })
      .catch((err: Error) => setError(err.message));
  }, [preset, start, end]);

  const currency = user.preferred_currency;
  const cards = data
    ? [
        ["Income", money(data.summary.income, currency)],
        ["Expenses", money(data.summary.expenses, currency)],
        ["Remaining balance", money(data.summary.balance, currency)],
        ["Savings", money(data.summary.savings, currency)],
        ["Savings rate", percent(data.summary.savings_rate)],
        ["Budget use", percent(data.budget_utilisation)],
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted">{data ? `${data.start} to ${data.end}` : "Calculated from your transactions"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className={controlClass} value={preset} onChange={(event) => setPreset(event.target.value)}>
            {PRESETS.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
          {preset === "custom" && (
            <>
              <input className={controlClass} type="date" value={start} onChange={(event) => setStart(event.target.value)} />
              <input className={controlClass} type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
            </>
          )}
        </div>
      </div>
      {error && <Banner tone="warn">{error}</Banner>}
      {data && data.summary.transaction_count === 0 && (
        <Empty title="No transactions in this range" body="Add one from Transactions, import a CSV, or load sample data in Settings." />
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-muted">{label}</p>
            <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
          </Card>
        ))}
      </div>
      {data?.budget_alerts.slice(0, 2).map((alert) => (
        <Banner key={alert} tone="warn">{alert}</Banner>
      ))}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-medium">Income and expenses</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={(data?.income_expense || []).map((row) => ({ ...row, income: Number(row.income), expenses: Number(row.expenses) }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="month" stroke="var(--muted)" fontSize={12} />
                <YAxis stroke="var(--muted)" fontSize={12} />
                <Tooltip />
                <Bar dataKey="income" fill="#1f7a4d" radius={4} />
                <Bar dataKey="expenses" fill="#b42318" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 font-medium">Expenses by category</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={(data?.categories || []).map((row) => ({ name: row.category, value: Number(row.amount) }))} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80}>
                  {(data?.categories || []).map((row, index) => (
                    <Cell key={row.category} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 font-medium">Weekly spending</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={(data?.weekly || []).map((row) => ({ week: row.week.slice(5), amount: Number(row.amount) }))}>
                <XAxis dataKey="week" stroke="var(--muted)" fontSize={12} />
                <YAxis stroke="var(--muted)" fontSize={12} />
                <Tooltip />
                <Bar dataKey="amount" fill="#0f6e6b" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 font-medium">Savings by month</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={(data?.income_expense || []).map((row) => ({ month: row.month, savings: Number(row.savings) }))}>
                <XAxis dataKey="month" stroke="var(--muted)" fontSize={12} />
                <YAxis stroke="var(--muted)" fontSize={12} />
                <Tooltip />
                <Bar dataKey="savings" fill="#c4841d" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-medium">Recent transactions</h2>
          <Link href="/transactions" className="text-sm text-accent">View all</Link>
        </div>
        <ul className="divide-y divide-line">
          {(data?.recent || []).map((row) => (
            <li key={row.id} className="flex items-center justify-between py-2 text-sm">
              <div>
                <p>{row.description}</p>
                <p className="text-xs text-muted">{row.date} · {row.category_name}</p>
              </div>
              <span className={row.type === "income" ? "text-good" : "text-bad"}>{money(row.amount, currency)}</span>
            </li>
          ))}
          {data && data.recent.length === 0 && <li className="py-4 text-sm text-muted">Nothing in this range yet.</li>}
        </ul>
      </Card>
    </div>
  );
}
