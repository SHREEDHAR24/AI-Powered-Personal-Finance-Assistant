export type User = {
  id: number;
  name: string;
  email: string;
  preferred_currency: string;
  alert_warn_pct: number;
  alert_critical_pct: number;
};

export function money(value: string | number | null | undefined, currency = "INR") {
  const amount = Number(value ?? 0);
  if (Number.isNaN(amount)) return "—";
  try {
    return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

export function percent(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value}%`;
}

export const PRESETS = [
  { id: "this_week", label: "This week" },
  { id: "this_month", label: "This month" },
  { id: "last_month", label: "Last month" },
  { id: "last_3_months", label: "Last three months" },
  { id: "custom", label: "Custom range" },
];

export const CHART_COLORS = ["#0f6e6b", "#c4841d", "#b42318", "#3d5a80", "#6b4c7a", "#2f6f4e", "#8c4a3a", "#4c6b5a"];
