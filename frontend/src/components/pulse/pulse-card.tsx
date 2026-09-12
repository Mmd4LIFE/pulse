"use client";

import { Megaphone, MoreHorizontal, Repeat2, Trash2, UserX } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { MediaGrid } from "@/components/pulse/media-grid";
import { PulseActions } from "@/components/pulse/pulse-actions";
import { PulseText } from "@/components/pulse/pulse-text";
import { UserAvatar } from "@/components/pulse/user-avatar";
import { VerifiedBadge } from "@/components/pulse/verified-badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDeletePulse } from "@/hooks/use-pulse-actions";
import { api } from "@/lib/api";
import { confirmAction } from "@/lib/telegram";
import { cn, relativeTime } from "@/lib/utils";
import type { Pulse, PulseRef } from "@/types/api";
import { toast } from "sonner";

interface Props {
  pulse: Pulse;
  /** Renders the pulse as the focused item of a thread: bigger, no truncation. */
  variant?: "timeline" | "detail";
  /** Draws the vertical line that joins this pulse to the reply beneath it. */
  connected?: boolean;
  className?: string;
}

export function PulseCard({
  pulse,
  variant = "timeline",
  connected = false,
  className,
}: Props) {
  const router = useRouter();
  const isDetail = variant === "detail";

  const open = () => router.push(`/pulse/${pulse.id}`);

  return (
    <article
      onClick={isDetail ? undefined : open}
      className={cn(
        "relative border-b border-border px-4 py-3 transition-colors",
        !isDetail && "cursor-pointer hover:bg-accent/40 active:bg-accent/60",
        className,
      )}
    >
      {pulse.repulsed_by ? (
        <div className="mb-1.5 flex items-center gap-2 pl-[52px] text-xs font-semibold text-muted-foreground">
          <Repeat2 className="h-3.5 w-3.5" />
          <Link
            href={`/u/${pulse.repulsed_by.username}`}
            onClick={(event) => event.stopPropagation()}
            className="hover:underline"
          >
            {pulse.repulsed_by.display_name} repulsed
          </Link>
        </div>
      ) : null}

      <div className={cn("flex gap-3", isDetail && "flex-col gap-3")}>
        <div className={cn("relative flex flex-col items-center", isDetail && "hidden")}>
          <UserAvatar user={pulse.author} />
          {connected ? (
            <span className="mt-1 w-0.5 flex-1 rounded-full bg-border" aria-hidden />
          ) : null}
        </div>

        <div className="min-w-0 flex-1">
          <header className="flex items-start gap-2">
            {isDetail ? <UserAvatar user={pulse.author} /> : null}

            <div className={cn("min-w-0 flex-1", isDetail && "flex flex-col")}>
              <div
                className={cn(
                  "flex min-w-0 items-center gap-1.5 text-base",
                  isDetail && "flex-col items-start gap-0",
                )}
              >
                <Link
                  href={`/u/${pulse.author.username}`}
                  onClick={(event) => event.stopPropagation()}
                  className="flex min-w-0 items-center gap-1 font-bold hover:underline"
                >
                  <bdi className="truncate">{pulse.author.display_name}</bdi>
                  {pulse.author.is_verified ? <VerifiedBadge /> : null}
                </Link>
                <span
                  className={cn(
                    "flex min-w-0 items-center gap-1.5 text-muted-foreground",
                    isDetail && "text-sm",
                  )}
                >
                  <span className="truncate">@{pulse.author.username}</span>
                  {!isDetail ? (
                    <>
                      <span aria-hidden>·</span>
                      <time dateTime={pulse.created_at} className="shrink-0">
                        {relativeTime(pulse.created_at)}
                      </time>
                    </>
                  ) : null}
                  {pulse.sent_to_channel && pulse.is_mine ? (
                    <Megaphone
                      className="h-3.5 w-3.5 shrink-0"
                      aria-label="Also posted to your channel"
                    />
                  ) : null}
                </span>
              </div>
            </div>

            <PulseMenu pulse={pulse} />
          </header>

          {pulse.reply_to && !connected ? (
            <p className="mt-0.5 text-sm text-muted-foreground">
              Replying to{" "}
              <Link
                href={`/u/${pulse.reply_to.author.username}`}
                onClick={(event) => event.stopPropagation()}
                className="entity-link"
              >
                @{pulse.reply_to.author.username}
              </Link>
            </p>
          ) : null}

          <div className="mt-1">
            <PulseText text={pulse.content} className={cn(isDetail && "text-lg")} />
            <MediaGrid media={pulse.media} />
            {pulse.quote_of ? <QuotedPulse quote={pulse.quote_of} /> : null}
          </div>

          {isDetail ? (
            <p className="mt-3 border-b border-border pb-3 text-sm text-muted-foreground">
              <time dateTime={pulse.created_at}>
                {new Date(pulse.created_at).toLocaleString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit",
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </time>
            </p>
          ) : null}

          <PulseActions pulse={pulse} />
        </div>
      </div>
    </article>
  );
}

function QuotedPulse({ quote }: { quote: PulseRef }) {
  const router = useRouter();

  if (quote.is_deleted) {
    return (
      <div className="mt-3 rounded-2xl border border-border px-3.5 py-3 text-sm text-muted-foreground">
        This pulse was deleted.
      </div>
    );
  }

  return (
    <div
      role="link"
      tabIndex={0}
      onClick={(event) => {
        event.stopPropagation();
        router.push(`/pulse/${quote.id}`);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") router.push(`/pulse/${quote.id}`);
      }}
      className="mt-3 cursor-pointer rounded-2xl border border-border px-3.5 py-3 transition-colors hover:bg-accent/40"
    >
      <div className="flex items-center gap-1.5 text-sm">
        <UserAvatar user={quote.author} className="h-5 w-5" linked={false} />
        <bdi className="truncate font-bold">{quote.author.display_name}</bdi>
        {quote.author.is_verified ? <VerifiedBadge className="h-3.5 w-3.5" /> : null}
        <span className="truncate text-muted-foreground">@{quote.author.username}</span>
        <span aria-hidden className="text-muted-foreground">
          ·
        </span>
        <time className="shrink-0 text-muted-foreground" dateTime={quote.created_at}>
          {relativeTime(quote.created_at)}
        </time>
      </div>
      <PulseText text={quote.content} className="mt-1 text-sm" />
      <MediaGrid media={quote.media} />
    </div>
  );
}

function PulseMenu({ pulse }: { pulse: Pulse }) {
  const remove = useDeletePulse();

  const onDelete = async (event: Event) => {
    event.preventDefault();
    if (await confirmAction("Delete this pulse? This cannot be undone.")) {
      remove.mutate(pulse.id);
    }
  };

  const onBlock = async (event: Event) => {
    event.preventDefault();
    if (await confirmAction(`Block @${pulse.author.username}?`)) {
      try {
        await api.block(pulse.author.username);
        toast.success(`Blocked @${pulse.author.username}.`);
      } catch {
        toast.error("Could not block that account.");
      }
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="More options"
          onClick={(event) => event.stopPropagation()}
          className="-mr-1.5 -mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <MoreHorizontal className="pulse-icon" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(event) => event.stopPropagation()}>
        {pulse.is_mine ? (
          <DropdownMenuItem destructive onSelect={onDelete}>
            <Trash2 />
            Delete pulse
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem destructive onSelect={onBlock}>
            <UserX />
            Block @{pulse.author.username}
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
