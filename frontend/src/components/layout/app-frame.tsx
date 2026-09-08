"use client";

/** The persistent chrome: header slot, scrollable content, tab bar, compose FAB. */

import { Feather } from "lucide-react";
import * as React from "react";

import { BottomNav } from "@/components/layout/bottom-nav";
import { Composer } from "@/components/pulse/composer";
import { useTelegramBackButton } from "@/hooks/use-back-button";
import { haptics } from "@/lib/telegram";
import { cn } from "@/lib/utils";

interface Props {
  children: React.ReactNode;
  header?: React.ReactNode;
  /** Hide the floating compose button on screens that have their own write flow. */
  hideCompose?: boolean;
}

export function AppFrame({ children, header, hideCompose = false }: Props) {
  const [composing, setComposing] = React.useState(false);
  useTelegramBackButton();

  return (
    <div className="app-shell">
      {header}
      <main className="flex-1">{children}</main>

      {!hideCompose ? (
        <>
          <button
            type="button"
            aria-label="Write a pulse"
            onClick={() => {
              haptics.tap("medium");
              setComposing(true);
            }}
            className={cn(
              "fixed bottom-[70px] right-[max(1rem,calc(50%-300px+1rem))] z-30",
              "flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/25",
              "tap-target transition-transform hover:scale-105",
            )}
            style={{ bottom: "calc(70px + var(--tg-safe-bottom))" }}
          >
            <Feather className="h-6 w-6" />
          </button>
          <Composer open={composing} onOpenChange={setComposing} />
        </>
      ) : null}

      <BottomNav />
    </div>
  );
}
