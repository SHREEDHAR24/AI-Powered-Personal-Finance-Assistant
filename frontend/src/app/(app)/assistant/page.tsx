"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";
import { Button, controlClass } from "@/components/ui";

type Conversation = { id: number; title: string };
type ChatMessage = { id?: number; role: string; content: string };

export default function AssistantPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  async function refreshList(selectId?: number) {
    const rows = await api<Conversation[]>("/api/conversations");
    setConversations(rows);
    const id = selectId || active || rows[0]?.id || null;
    setActive(id);
    if (id) setMessages(await api<ChatMessage[]>(`/api/conversations/${id}/messages`));
  }

  useEffect(() => {
    api<{ configured: boolean }>("/api/assistant/status").then((status) => setConfigured(status.configured)).catch(() => setConfigured(false));
    refreshList().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function openConversation(id: number) {
    setActive(id);
    setMessages(await api<ChatMessage[]>(`/api/conversations/${id}/messages`));
  }

  async function createConversation() {
    const created = await api<Conversation>("/api/conversations", { method: "POST", body: JSON.stringify({}) });
    await refreshList(created.id);
    setMessages([]);
  }

  async function stream(path: string, body?: string) {
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);
    setMessages((current) => [...current, { role: "assistant", content: "" }]);
    try {
      const response = await fetch(path, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body,
        signal: controller.signal,
      });
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (reader) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const dataLine = part.split("\n").find((line) => line.startsWith("data:"));
          if (!dataLine) continue;
          const event = JSON.parse(dataLine.slice(5).trim()) as { event: string; text?: string; message?: string };
          if (event.event === "token" && event.text) {
            setMessages((current) => {
              const next = [...current];
              const last = next[next.length - 1];
              if (last?.role === "assistant") next[next.length - 1] = { ...last, content: last.content + event.text };
              return next;
            });
          }
          if (event.event === "error" && event.message) {
            setMessages((current) => {
              const next = [...current];
              next[next.length - 1] = { role: "assistant", content: event.message || "" };
              return next;
            });
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setMessages((current) => {
          const next = [...current];
          next[next.length - 1] = { role: "assistant", content: "The request stopped before a full answer arrived." };
          return next;
        });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
      if (active) {
        const rows = await api<Conversation[]>("/api/conversations");
        setConversations(rows);
      }
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!active || !draft.trim()) return;
    const content = draft.trim();
    setDraft("");
    setMessages((current) => [...current, { role: "user", content }]);
    await stream(`/api/conversations/${active}/messages`, JSON.stringify({ content }));
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
      <aside className="space-y-2">
        <Button className="w-full" onClick={createConversation} type="button">New chat</Button>
        {conversations.map((item) => (
          <button
            key={item.id}
            className={`block w-full truncate rounded-xl px-3 py-2 text-left text-sm ${item.id === active ? "bg-accent-soft" : ""}`}
            onClick={() => openConversation(item.id)}
            type="button"
          >
            {item.title}
          </button>
        ))}
        {active && (
          <Button
            variant="ghost"
            className="w-full"
            type="button"
            onClick={async () => {
              await api(`/api/conversations/${active}/messages`, { method: "DELETE" });
              setMessages([]);
            }}
          >
            Clear chat
          </Button>
        )}
      </aside>
      <section className="flex min-h-[70vh] flex-col rounded-2xl border border-line bg-surface">
        <div className="border-b border-line px-4 py-3 text-sm text-muted">
          {configured === false
            ? "No LLM key is configured. Questions will explain how to set one. Numbers elsewhere in FinMate do not depend on it."
            : "Answers that mention amounts come from FinMate tools, not from the model guessing."}
        </div>
        <div className="flex-1 space-y-4 overflow-auto px-4 py-4">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={message.role === "user" ? "ml-8" : "mr-8"}>
              <p className="mb-1 text-xs uppercase tracking-wide text-muted">{message.role}</p>
              <div className="prose prose-sm max-w-none text-sm">
                <ReactMarkdown>{message.content || "…"}</ReactMarkdown>
              </div>
            </div>
          ))}
          {messages.length === 0 && <p className="text-sm text-muted">Ask about a category, a month, a budget, or next month’s estimate.</p>}
        </div>
        <form className="flex gap-2 border-t border-line p-3" onSubmit={send}>
          <input className={controlClass} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about your records" disabled={!active || streaming} />
          {streaming ? (
            <Button type="button" variant="ghost" onClick={() => abortRef.current?.abort()}>Stop</Button>
          ) : (
            <Button type="submit" disabled={!active}>Send</Button>
          )}
          <Button
            type="button"
            variant="soft"
            disabled={!active || streaming}
            onClick={async () => {
              setMessages((current) => (current[current.length - 1]?.role === "assistant" ? current.slice(0, -1) : current));
              await stream(`/api/conversations/${active}/regenerate`);
            }}
          >
            Regenerate
          </Button>
        </form>
      </section>
    </div>
  );
}
