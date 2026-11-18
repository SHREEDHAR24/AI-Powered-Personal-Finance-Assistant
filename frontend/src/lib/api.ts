export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body && !isForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = data.detail.map((item: { msg?: string }) => item.msg || "Invalid").join(", ");
    } catch {
      /* keep status text */
    }
    throw new ApiError(response.status, detail);
  }
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return response.json();
  return undefined as T;
}

export async function download(path: string, filename: string) {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) throw new ApiError(response.status, "Download failed");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
