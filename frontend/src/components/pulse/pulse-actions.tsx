"use client";

import { Bookmark, Heart, MessageCircle, Repeat2, Share } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Composer } from "@/components/pulse/composer";
import { usePulseActions } from "@/hooks/use-pulse-actions";
import { openExternal } from "@/lib/telegram";
import { cn, compactNumber } from "@/lib/utils";
import type { Pulse } from "@/types/api";
import * as React from "react";

interface ActionProps {
  pulse: Pulse;
  botUsername?: string;
}

export function PulseActions({ pulse }: ActionProps) {
  const router = useRouter();
  const { like, repulse, bookmark } = usePulseActions();
  const [replyOpen, setReplyOpen] = React.useState(false);

  const stop = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <>
      <div className="mt-2.5 flex items-center justify-between pr-6 text-muted-foreground">
        <ActionButton
          label="Reply"
          count={pulse.reply_count}
          onClick={(event) => {
            stop(event);
            setReplyOpen(true);
          }}
          hoverClass="group-hover:bg-primary/10 group-hover:text-primary"
        >
          <MessageCircle className="pulse-icon" />
        </ActionButton>

        <ActionButton
          label="Repulse"
          count={pulse.repulse_count}
          active={pulse.is_repulsed}
          activeClass="text-repulse"
          hoverClass="group-hover:bg-repulse/10 group-hover:text-repulse"
          onClick={(event) => {
            stop(event);
            repulse.mutate({ id: pulse.id, on: !pulse.is_repulsed });
          }}
        >
          <Repeat2 className="pulse-icon" />
        </ActionButton>

        <ActionButton
          label="Like"
          count={pulse.like_count}
          active={pulse.is_liked}
          activeClass="text-like"
          hoverClass="group-hover:bg-like/10 group-hover:text-like"
          onClick={(event) => {
            stop(event);
            like.mutate({ id: pulse.id, on: !pulse.is_liked });
          }}
        >
          <Heart
            className={cn(
              "pulse-icon",
              pulse.is_liked && "animate-pop fill-current",
            )}
          />
        </ActionButton>

        <ActionButton
          label="Bookmark"
          active={pulse.is_bookmarked}
          activeClass="text-primary"
          hoverClass="group-hover:bg-primary/10 group-hover:text-primary"
          onClick={(event) => {
            stop(event);
            bookmark.mutate({ id: pulse.id, on: !pulse.is_bookmarked });
          }}
        >
          <Bookmark
            className={cn(
              "pulse-icon",
              pulse.is_bookmarked && "animate-pop fill-current",
            )}
          />
        </ActionButton>

        <ActionButton
          label="Share"
          hoverClass="group-hover:bg-primary/10 group-hover:text-primary"
          onClick={(event) => {
            stop(event);
            void sharePulse(pulse);
          }}
        >
          <Share className="pulse-icon" />
        </ActionButton>
      </div>

      <Composer
        open={replyOpen}
        onOpenChange={setReplyOpen}
        replyTo={pulse}
        onPosted={() => router.refresh()}
      />
    </>
  );
}

interface ActionButtonProps {
  children: React.ReactNode;
  label: string;
  count?: number;
  active?: boolean;
  activeClass?: string;
  hoverClass?: string;
  onClick: (event: React.MouseEvent) => void;
}

function ActionButton({
  children,
  label,
  count,
  active,
  activeClass,
  hoverClass,
  onClick,
}: ActionButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
      className={cn("group -ml-1.5 flex items-center gap-1 text-xs", active && activeClass)}
    >
      <span
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
          hoverClass,
        )}
      >
        {children}
      </span>
      {count !== undefined && count > 0 ? (
        <span className="tabular-nums font-medium">{compactNumber(count)}</span>
      ) : null}
    </button>
  );
}

async function sharePulse(pulse: Pulse) {
  const url = `${window.location.origin}/pulse/${pulse.id}`;
  const text = `${pulse.author.display_name} on Pulse`;

  if (navigator.share) {
    try {
      await navigator.share({ title: "Pulse", text, url });
      return;
    } catch {
      // The user dismissed the sheet; fall through to copying.
    }
  }

  try {
    await navigator.clipboard.writeText(url);
    toast.success("Link copied.");
  } catch {
    openExternal(url);
  }
}
