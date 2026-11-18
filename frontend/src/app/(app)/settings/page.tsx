"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useUser } from "@/lib/session";
import { Button, Card, controlClass, Field } from "@/components/ui";

type Category = { id: number; name: string; transaction_type: string };
type Rule = { id: number; pattern: string; category_name: string };

export default function SettingsPage() {
  const user = useUser();
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);

  async function loadRules() {
    setCategories(await api<Category[]>("/api/categories"));
    setRules(await api<Rule[]>("/api/category-rules"));
  }

  useEffect(() => {
    loadRules().catch(() => undefined);
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({
          name: form.get("name"),
          preferred_currency: form.get("preferred_currency"),
          alert_warn_pct: Number(form.get("alert_warn_pct")),
          alert_critical_pct: Number(form.get("alert_critical_pct")),
        }),
      });
      setMessage("Saved. Reload the page to see the new currency symbol. Amounts are not converted.");
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  async function addCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api("/api/categories", {
      method: "POST",
      body: JSON.stringify({ name: form.get("name"), transaction_type: form.get("transaction_type") }),
    });
    event.currentTarget.reset();
    await loadRules();
  }

  async function addRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api("/api/category-rules", {
      method: "POST",
      body: JSON.stringify({ pattern: form.get("pattern"), category_id: Number(form.get("category_id")) }),
    });
    event.currentTarget.reset();
    await loadRules();
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted">Changing currency changes the symbol only. Past amounts stay as you entered them.</p>
      </div>
      {message && <p className="text-sm text-good">{message}</p>}
      {error && <p className="text-sm text-bad">{error}</p>}
      <Card>
        <form className="grid gap-3 md:grid-cols-2" onSubmit={saveProfile}>
          <Field label="Name"><input className={controlClass} name="name" defaultValue={user.name} /></Field>
          <Field label="Currency">
            <select className={controlClass} name="preferred_currency" defaultValue={user.preferred_currency}>
              {["INR", "USD", "EUR", "GBP"].map((code) => <option key={code}>{code}</option>)}
            </select>
          </Field>
          <Field label="First budget alert %"><input className={controlClass} name="alert_warn_pct" type="number" defaultValue={user.alert_warn_pct} /></Field>
          <Field label="Higher budget alert %"><input className={controlClass} name="alert_critical_pct" type="number" defaultValue={user.alert_critical_pct} /></Field>
          <Button type="submit">Save profile</Button>
        </form>
      </Card>
      <Card>
        <h2 className="font-medium">Sample data</h2>
        <p className="mt-1 text-sm text-muted">Loads six months of labelled demo transactions on this account. You can remove only those rows later.</p>
        <div className="mt-3 flex gap-2">
          <Button type="button" onClick={async () => { const result = await api<{ loaded: number }>("/api/demo/load", { method: "POST" }); setMessage(`Loaded ${result.loaded} sample transactions.`); }}>Load sample finances</Button>
          <Button type="button" variant="ghost" onClick={async () => { const result = await api<{ deleted: number }>("/api/demo", { method: "DELETE" }); setMessage(`Removed ${result.deleted} sample transactions.`); }}>Remove sample data</Button>
        </div>
      </Card>
      <Card>
        <h2 className="mb-3 font-medium">Custom category</h2>
        <form className="flex flex-wrap gap-2" onSubmit={addCategory}>
          <input className={controlClass} name="name" placeholder="Category name" required />
          <select className={controlClass} name="transaction_type">
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
          <Button type="submit">Add</Button>
        </form>
      </Card>
      <Card>
        <h2 className="mb-3 font-medium">Your categorisation rules</h2>
        <p className="mb-3 text-sm text-muted">If a description contains the pattern, this category wins over keywords.</p>
        <form className="flex flex-wrap gap-2" onSubmit={addRule}>
          <input className={controlClass} name="pattern" placeholder="Keyword, such as landlord" required />
          <select className={controlClass} name="category_id">
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <Button type="submit">Add rule</Button>
        </form>
        <ul className="mt-3 text-sm">
          {rules.map((rule) => (
            <li key={rule.id} className="flex justify-between border-b border-line py-2">
              <span>{rule.pattern} → {rule.category_name}</span>
              <button className="text-bad" type="button" onClick={async () => { await api(`/api/category-rules/${rule.id}`, { method: "DELETE" }); await loadRules(); }}>Delete</button>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="font-medium text-bad">Delete account</h2>
        <p className="mt-1 text-sm text-muted">This removes your login and every financial row stored for you.</p>
        <Button
          className="mt-3"
          variant="danger"
          type="button"
          onClick={async () => {
            if (!confirm("Delete your FinMate account and all of its data?")) return;
            await api("/api/auth/me", { method: "DELETE" });
            router.replace("/");
          }}
        >
          Delete my data
        </Button>
      </Card>
    </div>
  );
}
