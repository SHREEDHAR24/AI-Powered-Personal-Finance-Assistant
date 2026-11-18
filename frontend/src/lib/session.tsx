"use client";

import { createContext, useContext } from "react";
import { User } from "@/lib/format";

const SessionContext = createContext<User | null>(null);

export function SessionProvider({ user, children }: { user: User; children: React.ReactNode }) {
  return <SessionContext.Provider value={user}>{children}</SessionContext.Provider>;
}

export function useUser() {
  const user = useContext(SessionContext);
  if (!user) throw new Error("Missing session");
  return user;
}
