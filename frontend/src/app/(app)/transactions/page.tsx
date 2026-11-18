"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { money } from "@/lib/format";
import { useUser } from "@/lib/session";
import { Button, Card, controlClass, Empty, Field, Modal } from "@/components/ui";

type Category = { id: number; name: string; transaction_type: string };
type Tx = {
  id: number;
  date: string;
  description: string;
  merchant: string | null;
  amount: string;
  type: string;
  category_id: number;
  category_name: string;
  payment_method: string;
  notes: string | null;
};

const METHODS = ["UPI", "Cash", "Debit Card", "Credit Card", "Net Banking", "Wallet", "Other"];

export default function TransactionsPage() {
  const user = useUser();
  const [items, setItems] = useState<Tx[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [method, setMethod] = useState("");
  const [sort, setSort] = useState("date_desc");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Tx | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const params = new URLSearchParams({ sort, limit: "100" });
    if (search) params.set("search", search);
    if (type) params.set("type", type);
    if (categoryId) params.set("category_id", categoryId);
    if (method) params.set("payment_method", method);
    if (minAmount) params.set("min_amount", minAmount);
    if (maxAmount) params.set("max_amount", maxAmount);
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    const data = await api<{ total: number; items: Tx[] }>(`/api/transactions?${params}`);
    setItems(data.items);
    setTotal(data.total);
  }

  useEffect(() => {
    api<Category[]>("/api/categories").then(setCategories).catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, type, categoryId, method, sort, minAmount, maxAmount, start, end]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      date: form.get("date"),
      description: form.get("description"),
      amount: form.get("amount"),
      type: form.get("type"),
      category_id: Number(form.get("category_id")) || null,
      payment_method: form.get("payment_method"),
      merchant: form.get("merchant") || null,
      notes: form.get("notes") || null,
    };
    if (!editing && !payload.category_id) delete (payload as { category_id?: number | null }).category_id;
    try {
      if (editing) {
        await api(`/api/transactions/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await api("/api/transactions", { method: "POST", body: JSON.stringify(payload) });
      }
      setOpen(false);
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  async function remove(id: number) {
    if (!confirm("Delete this transaction?")) return;
    await api(`/api/transactions/${id}`, { method: "DELETE" });
    await load();
  }

  const txType = editing?.type || "expense";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Transactions</h1>
          <p className="text-sm text-muted">{total} matching records</p>
        </div>
        <Button onClick={() => { setEditing(null); setOpen(true); }}>Add transaction</Button>
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
      <Card className="grid gap-3 md:grid-cols-4">
        <input className={controlClass} placeholder="Search description" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select className={controlClass} value={type} onChange={(event) => setType(event.target.value)}>
          <option value="">Income and expense</option>
          <option value="expense">Expense</option>
          <option value="income">Income</option>
        </select>
        <select className={controlClass} value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
          <option value="">All categories</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>{category.name} ({category.transaction_type})</option>
          ))}
        </select>
        <select className={controlClass} value={method} onChange={(event) => setMethod(event.target.value)}>
          <option value="">All payment methods</option>
          {METHODS.map((item) => <option key={item}>{item}</option>)}
        </select>
        <input className={controlClass} type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        <input className={controlClass} type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
        <input className={controlClass} placeholder="Min amount" value={minAmount} onChange={(event) => setMinAmount(event.target.value)} />
        <input className={controlClass} placeholder="Max amount" value={maxAmount} onChange={(event) => setMaxAmount(event.target.value)} />
        <select className={controlClass} value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="date_desc">Newest first</option>
          <option value="date_asc">Oldest first</option>
          <option value="amount_desc">Highest amount</option>
          <option value="amount_asc">Lowest amount</option>
        </select>
      </Card>
      {items.length === 0 ? (
        <Empty title="No transactions yet" body="Add one manually or import a bank CSV." />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Description</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Method</th>
                <th className="px-4 py-3 font-medium">Amount</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t border-line">
                  <td className="px-4 py-3 whitespace-nowrap">{row.date}</td>
                  <td className="px-4 py-3">
                    <p>{row.description}</p>
                    {row.merchant && <p className="text-xs text-muted">{row.merchant}</p>}
                  </td>
                  <td className="px-4 py-3">{row.category_name}</td>
                  <td className="px-4 py-3">{row.payment_method}</td>
                  <td className={`px-4 py-3 tabular-nums ${row.type === "income" ? "text-good" : "text-bad"}`}>
                    {money(row.amount, user.preferred_currency)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button className="mr-3 text-accent" onClick={() => { setEditing(row); setOpen(true); }} type="button">Edit</button>
                    <button className="text-bad" onClick={() => remove(row.id)} type="button">Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && (
        <Modal title={editing ? "Edit transaction" : "Add transaction"} onClose={() => setOpen(false)}>
          <form className="space-y-3" onSubmit={save}>
            <Field label="Date"><input className={controlClass} type="date" name="date" required defaultValue={editing?.date || new Date().toISOString().slice(0, 10)} /></Field>
            <Field label="Description"><input className={controlClass} name="description" required defaultValue={editing?.description} /></Field>
            <Field label="Amount"><input className={controlClass} name="amount" required defaultValue={editing?.amount} /></Field>
            <Field label="Type">
              <select className={controlClass} name="type" defaultValue={txType}>
                <option value="expense">Expense</option>
                <option value="income">Income</option>
              </select>
            </Field>
            <Field label={editing ? "Category" : "Category (leave blank to predict)"}>
              <select className={controlClass} name="category_id" defaultValue={editing?.category_id || ""}>
                {!editing && <option value="">Predict from the description</option>}
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name} · {category.transaction_type}</option>
                ))}
              </select>
            </Field>
            <Field label="Payment method">
              <select className={controlClass} name="payment_method" defaultValue={editing?.payment_method || "UPI"}>
                {METHODS.map((item) => <option key={item}>{item}</option>)}
              </select>
            </Field>
            <Field label="Merchant"><input className={controlClass} name="merchant" defaultValue={editing?.merchant || ""} /></Field>
            <Field label="Notes"><textarea className={controlClass} name="notes" defaultValue={editing?.notes || ""} /></Field>
            <Button type="submit">Save</Button>
          </form>
        </Modal>
      )}
    </div>
  );
}
