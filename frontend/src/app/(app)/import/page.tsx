"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button, Card, controlClass, Field } from "@/components/ui";

type Analyse = {
  preview_id: string;
  columns: string[];
  row_count: number;
  suggested_mapping: Record<string, string | null>;
};
type PreviewRow = {
  index: number;
  status: string;
  reason?: string;
  date?: string;
  description?: string;
  amount?: string;
  type?: string;
  category_id?: number;
  category_name?: string;
  confidence?: number;
};
type Category = { id: number; name: string; transaction_type: string };
type History = { id: number; file_name: string; import_date: string; total_rows: number; successful_rows: number; duplicate_rows: number; invalid_rows: number };

const FIELDS = ["date", "description", "debit", "credit", "amount", "type", "balance", "merchant", "notes", "payment_method"];

export default function ImportPage() {
  const [analyse, setAnalyse] = useState<Analyse | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [preview, setPreview] = useState<{ total_rows: number; ready_rows: number; duplicate_rows: number; invalid_rows: number; rows: PreviewRow[]; invalid: PreviewRow[] } | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [choices, setChoices] = useState<Record<number, number>>({});
  const [history, setHistory] = useState<History[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refreshHistory() {
    setHistory(await api<History[]>("/api/imports"));
  }

  useEffect(() => {
    api<Category[]>("/api/categories").then(setCategories).catch(() => undefined);
    refreshHistory().catch(() => undefined);
  }, []);

  async function upload(file: File) {
    setError("");
    setPreview(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const result = await api<Analyse>("/api/imports/analyse", { method: "POST", body });
      setAnalyse(result);
      setMapping(result.suggested_mapping);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    }
  }

  async function runPreview() {
    if (!analyse) return;
    try {
      const result = await api<NonNullable<typeof preview>>("/api/imports/preview", {
        method: "POST",
        body: JSON.stringify({ preview_id: analyse.preview_id, mapping }),
      });
      setPreview(result);
      const next: Record<number, number> = {};
      result.rows.forEach((row) => {
        if (row.category_id) next[row.index] = row.category_id;
      });
      setChoices(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not preview");
    }
  }

  async function commit() {
    if (!analyse || !preview) return;
    const rows = preview.rows.filter((row) => row.status === "ready").map((row) => ({
      index: row.index,
      category_id: choices[row.index] || row.category_id,
      include: true,
    }));
    try {
      const result = await api<{ successful_rows: number }>("/api/imports/commit", {
        method: "POST",
        body: JSON.stringify({ preview_id: analyse.preview_id, rows }),
      });
      setMessage(`Saved ${result.successful_rows} transactions.`);
      setAnalyse(null);
      setPreview(null);
      await refreshHistory();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Import statements</h1>
        <p className="text-sm text-muted">CSV only. Nothing is saved until you confirm the preview. Bank passwords are never requested.</p>
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
      {message && <p className="text-sm text-good">{message}</p>}
      <Card>
        <Field label="Bank CSV">
          <input
            className={controlClass}
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload(file);
            }}
          />
        </Field>
        {analyse && <p className="mt-3 text-sm text-muted">{analyse.row_count} rows · columns: {analyse.columns.join(", ")}</p>}
      </Card>
      {analyse && (
        <Card>
          <h2 className="mb-3 font-medium">Map columns</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {FIELDS.map((field) => (
              <Field key={field} label={field}>
                <select
                  className={controlClass}
                  value={mapping[field] || ""}
                  onChange={(event) => setMapping({ ...mapping, [field]: event.target.value || null })}
                >
                  <option value="">Not in file</option>
                  {analyse.columns.map((column) => <option key={column}>{column}</option>)}
                </select>
              </Field>
            ))}
          </div>
          <Button className="mt-4" onClick={runPreview} type="button">Preview rows</Button>
        </Card>
      )}
      {preview && (
        <Card>
          <p className="text-sm">
            {preview.total_rows} detected · {preview.ready_rows} ready · {preview.duplicate_rows} duplicates · {preview.invalid_rows} invalid
          </p>
          <div className="mt-3 max-h-[420px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-muted">
                <tr>
                  <th className="py-2">Date</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th>Category</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.index} className="border-t border-line">
                    <td className="py-2 pr-2">{row.date}</td>
                    <td className="pr-2">{row.description}</td>
                    <td className="pr-2">{row.amount}</td>
                    <td className="pr-2">
                      {row.status === "ready" ? (
                        <select
                          className={controlClass}
                          value={choices[row.index] || ""}
                          onChange={(event) => setChoices({ ...choices, [row.index]: Number(event.target.value) })}
                        >
                          {categories.filter((category) => category.transaction_type === row.type).map((category) => (
                            <option key={category.id} value={category.id}>{category.name}</option>
                          ))}
                        </select>
                      ) : row.category_name}
                      {row.confidence !== undefined && <span className="ml-2 text-xs text-muted">{Math.round(row.confidence * 100)}%</span>}
                    </td>
                    <td>{row.status}{row.reason ? ` · ${row.reason}` : ""}</td>
                  </tr>
                ))}
                {preview.invalid.map((row) => (
                  <tr key={`bad-${row.index}`} className="border-t border-line text-bad">
                    <td className="py-2" colSpan={4}>Row {row.index}</td>
                    <td>{row.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button className="mt-4" onClick={commit} disabled={preview.ready_rows === 0} type="button">Save ready rows</Button>
        </Card>
      )}
      <Card>
        <h2 className="mb-3 font-medium">Import history</h2>
        {history.length === 0 && <p className="text-sm text-muted">No files imported yet.</p>}
        <ul className="space-y-2 text-sm">
          {history.map((item) => (
            <li key={item.id} className="flex flex-wrap justify-between gap-2 border-b border-line py-2">
              <span>{item.file_name}</span>
              <span className="text-muted">{item.successful_rows} saved · {item.duplicate_rows} duplicates · {item.invalid_rows} invalid</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
