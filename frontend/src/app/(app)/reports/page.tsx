"use client";

import { useState } from "react";
import { api, download } from "@/lib/api";
import { money, percent } from "@/lib/format";
import { useUser } from "@/lib/session";
import { Button, Card, controlClass } from "@/components/ui";

type Report = {
  label: string;
  summary: { income: string; expenses: string; balance: string; savings_rate: number | null };
  computed_summary: string;
  ai_commentary: string | null;
  ai_error?: string;
  categories: { category: string; amount: string }[];
};

export default function ReportsPage() {
  const user = useUser();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [report, setReport] = useState<Report | null>(null);
  const currency = user.preferred_currency;

  async function load(ai = false) {
    const data = await api<Report>(`/api/reports/monthly?month=${month}&year=${year}&ai=${ai}`);
    setReport(data);
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Reports</h1>
        <p className="text-sm text-muted">The summary is calculated. AI commentary is added only when a key is configured, and it is kept separate.</p>
      </div>
      <Card className="flex flex-wrap items-end gap-3">
        <label className="text-sm">Month
          <input className={`${controlClass} mt-1`} type="number" min={1} max={12} value={month} onChange={(event) => setMonth(Number(event.target.value))} />
        </label>
        <label className="text-sm">Year
          <input className={`${controlClass} mt-1`} type="number" value={year} onChange={(event) => setYear(Number(event.target.value))} />
        </label>
        <Button type="button" onClick={() => load(false)}>Show month</Button>
        <Button type="button" variant="soft" onClick={() => load(true)}>Add AI commentary</Button>
        <Button type="button" variant="ghost" onClick={() => download(`/api/reports/monthly/export?month=${month}&year=${year}&format=csv`, `finmate-${year}-${month}.csv`)}>CSV</Button>
        <Button type="button" variant="ghost" onClick={() => download(`/api/reports/monthly/export?month=${month}&year=${year}&format=pdf`, `finmate-${year}-${month}.pdf`)}>PDF</Button>
        <Button type="button" variant="ghost" onClick={() => download(`/api/reports/yearly/export?year=${year}&format=csv`, `finmate-${year}.csv`)}>Year CSV</Button>
        <Button type="button" variant="ghost" onClick={() => download(`/api/reports/yearly/export?year=${year}&format=pdf`, `finmate-${year}.pdf`)}>Year PDF</Button>
      </Card>
      {report && (
        <Card>
          <h2 className="text-lg font-medium">{report.label}</h2>
          <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
            <p>Income {money(report.summary.income, currency)}</p>
            <p>Expenses {money(report.summary.expenses, currency)}</p>
            <p>Balance {money(report.summary.balance, currency)}</p>
            <p>Savings rate {percent(report.summary.savings_rate)}</p>
          </div>
          <h3 className="mt-4 font-medium">Calculated summary</h3>
          <p className="mt-1 text-sm">{report.computed_summary}</p>
          <h3 className="mt-4 font-medium">Categories</h3>
          <ul className="mt-2 text-sm">
            {report.categories.map((item) => (
              <li key={item.category} className="flex justify-between border-b border-line py-1">
                <span>{item.category}</span><span>{money(item.amount, currency)}</span>
              </li>
            ))}
          </ul>
          <h3 className="mt-4 font-medium">AI commentary</h3>
          {report.ai_commentary ? (
            <p className="mt-1 rounded-xl bg-accent-soft p-3 text-sm">{report.ai_commentary}</p>
          ) : (
            <p className="mt-1 text-sm text-muted">
              {report.ai_error || "No AI paragraph was added. Set LLM_API_KEY if you want one. The figures above do not depend on it."}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
