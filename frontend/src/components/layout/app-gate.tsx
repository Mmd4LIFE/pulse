"use client";

/** Holds the UI back until the session is established, and shows why if it fails. */

import { AlertCircle, RefreshCw } from "lucide-react";

import { PulseMark } from "@/components/layout/pulse-mark";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";

export function AppGate({ children }: { children: React.ReactNode }) {
  const { status, error, retry } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-5 bg-background">
        <PulseMark className="h-14 w-14 animate-pulse text-primary" />
        <p className="text-sm font-medium text-muted-foreground">Waking up Pulse…</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 px-8 text-center">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <div className="space-y-1.5">
          <h1 className="text-lg font-bold">Pulse could not start</h1>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
        <Button onClick={retry} className="mt-1">
          <RefreshCw className="h-4 w-4" />
          Try again
        </Button>
      </div>
    );
  }

  return <>{children}</>;
}
