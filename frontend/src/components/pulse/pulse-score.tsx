"use client";

/**
 * The Pulse Score: what the model made of a pulse, out of ten.
 *
 * Read like an IMDb rating -- one number, one decimal place, the same every
 * time you look at it. It says something about the writing, which is why it is
 * shown up in the header with the author rather than down among the likes and
 * reposts, which say something about the readers.
 */

import { Sparkles } from "lucide-react";
import * as React from "react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Pulse } from "@/types/api";

/** How long after posting a score is still worth waiting for. */
const WORTH_WAITING_MS = 3 * 60 * 1000;
const POLL_MS = 3000;
const POLL_LIMIT = 12;

/** Bands, so the number reads at a glance before it is read as a number. */
function tone(score: number): string {
  if (score >= 8) return "bg-emerald-500/12 text-emerald-700";
  if (score >= 6.5) return "bg-primary/12 text-primary";
  if (score >= 4) return "bg-amber-500/14 text-amber-700";
  return "bg-muted text-muted-foreground";
}

export function formatScore(score: number): string {
  return score.toFixed(1);
}

/**
 * The score, or a quiet placeholder while the model is still reading.
 *
 * A pulse posted a moment ago has no score yet -- it is settled just after the
 * response -- so a fresh one is asked after rather than left blank forever.
 */
export function PulseScore({
  pulse,
  size = "sm",
  className,
}: {
  pulse: Pulse;
  size?: "sm" | "lg";
  className?: string;
}) {
  const score = useScore(pulse);
  const large = size === "lg";

  const shell = cn(
    "inline-flex shrink-0 items-center gap-1 rounded-full font-bold tabular-nums",
    large ? "px-2.5 py-1 text-sm" : "px-2 py-0.5 text-xs",
    className,
  );

  if (score === null) {
    if (!isWorthWaitingFor(pulse)) return null;
    return (
      <span
        className={cn(shell, "bg-muted text-muted-foreground")}
        aria-label="Scoring this pulse"
        title="Scoring…"
      >
        <Sparkles
          className={cn("animate-pulse", large ? "h-4 w-4" : "h-3 w-3")}
        />
        <span className="opacity-60">·</span>
      </span>
    );
  }

  return (
    <span
      className={cn(shell, tone(score))}
      aria-label={`Pulse Score ${formatScore(score)} out of 10`}
      title={`Pulse Score ${formatScore(score)}/10`}
    >
      <Sparkles className={large ? "h-4 w-4" : "h-3 w-3"} />
      {formatScore(score)}
    </span>
  );
}

function isWorthWaitingFor(pulse: Pulse): boolean {
  return Date.now() - new Date(pulse.created_at).getTime() < WORTH_WAITING_MS;
}

function useScore(pulse: Pulse): number | null {
  const [polled, setPolled] = React.useState<number | null>(null);
  // The pulse itself wins: the list it came from may have refetched with the
  // score already in it, which is fresher than anything asked for here.
  const score = pulse.score ?? polled;

  React.useEffect(() => {
    if (score !== null || !isWorthWaitingFor(pulse)) return;

    let cancelled = false;
    let timer: number | undefined;
    let tries = 0;

    const ask = async () => {
      tries += 1;
      try {
        const fresh = await api.getPulse(pulse.id);
        if (!cancelled && fresh.score !== null) {
          setPolled(fresh.score);
          return;
        }
      } catch {
        /* the next tick can try again */
      }
      if (!cancelled && tries < POLL_LIMIT) {
        timer = window.setTimeout(ask, POLL_MS);
      }
    };

    timer = window.setTimeout(ask, POLL_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pulse.id, score]);

  return score;
}
