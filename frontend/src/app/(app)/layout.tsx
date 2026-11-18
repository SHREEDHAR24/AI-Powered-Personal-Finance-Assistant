"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/shell";
import { api } from "@/lib/api";
import { User } from "@/lib/format";
import { SessionProvider } from "@/lib/session";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!user) {
    return <div className="grid min-h-screen place-items-center text-sm text-muted">Opening your account…</div>;
  }

  return (
    <SessionProvider user={user}>
      <Shell user={user}>{children}</Shell>
    </SessionProvider>
  );
}
