"use client";

/**
 * Where a pulse goes when you tap share.
 *
 * Both routes end in Telegram's own chat picker, so the user chooses who sees
 * it and the app never learns where it went. The link is the cheap one; the
 * picture is rendered here, handed to the backend, and shared back through
 * Telegram as a prepared message.
 */

import { ImageIcon, Link2, Loader2, Send } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import {
  CARD_WIDTH,
  ShareCard,
  renderShareCard,
} from "@/components/pulse/share-card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import {
  canShareMessage,
  haptics,
  openExternal,
  shareMessage,
} from "@/lib/telegram";
import { cn } from "@/lib/utils";
import type { Pulse } from "@/types/api";

const BOT_USERNAME = process.env.NEXT_PUBLIC_BOT_USERNAME;

/**
 * The address to give someone else.
 *
 * The Mini App cannot be opened from a bare web link, so a share points at the
 * bot, which answers a ``pulse_<id>`` payload with a button into the app.
 */
export function pulseLink(pulseId: number): string {
  if (BOT_USERNAME)
    return `https://t.me/${BOT_USERNAME}?start=pulse_${pulseId}`;
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `${origin}/pulse/${pulseId}`;
}

interface Props {
  pulse: Pulse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ShareSheet({ pulse, open, onOpenChange }: Props) {
  const cardRef = React.useRef<HTMLDivElement>(null);
  const [busy, setBusy] = React.useState(false);

  const link = pulseLink(pulse.id);

  const shareLink = () => {
    haptics.tap();
    const text = `${pulse.author.display_name} on Pulse`;
    openExternal(
      `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`,
    );
    onOpenChange(false);
  };

  const sharePicture = async () => {
    if (busy) return;
    haptics.tap();

    if (!canShareMessage()) {
      toast.error(
        "Update Telegram to send pictures, or share the link instead.",
      );
      return;
    }

    const node = cardRef.current;
    if (!node) return;

    setBusy(true);
    try {
      const card = await renderShareCard(node);
      const prepared = await api.sharePulseCard(pulse.id, card);
      const sent = await shareMessage(prepared.prepared_message_id);
      if (sent) {
        haptics.notify("success");
        onOpenChange(false);
      }
    } catch {
      toast.error("Could not make a picture of this pulse.");
    } finally {
      setBusy(false);
    }
  };

  const copyLink = async () => {
    haptics.tap();
    try {
      await navigator.clipboard.writeText(link);
      toast.success("Link copied.");
      onOpenChange(false);
    } catch {
      openExternal(link);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-4">
        <DialogHeader>
          <DialogTitle>Share this pulse</DialogTitle>
          <DialogDescription>
            Telegram will ask you who to send it to.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-2">
          <Choice
            icon={<Send className="h-5 w-5" />}
            title="Send as a link"
            hint="Opens straight into Pulse for whoever taps it."
            onClick={shareLink}
          />
          <Choice
            icon={
              busy ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <ImageIcon className="h-5 w-5" />
              )
            }
            title="Send as a picture"
            hint="A card of the pulse, with a button back to it."
            onClick={sharePicture}
            disabled={busy}
          />
          <Choice
            icon={<Link2 className="h-5 w-5" />}
            title="Copy link"
            hint={link.replace(/^https:\/\//, "")}
            onClick={copyLink}
          />
        </div>

        {/*
          Rendered for real, off to the side: html-to-image can only photograph
          a node the browser has actually laid out. It is only mounted while the
          sheet is open, so a timeline of cards costs nothing.
        */}
        <div
          aria-hidden
          className="pointer-events-none fixed left-[-9999px] top-0"
          style={{ width: CARD_WIDTH }}
        >
          <ShareCard ref={cardRef} pulse={pulse} />
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Choice({
  icon,
  title,
  hint,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  title: string;
  hint: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex items-center gap-3.5 rounded-2xl border border-border bg-card px-4 py-3 text-left transition-colors",
        disabled ? "opacity-60" : "hover:bg-accent",
      )}
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-bold">{title}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {hint}
        </span>
      </span>
    </button>
  );
}
