"use client";

/** The write surface, used for new pulses, replies and quotes alike. */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Loader2, X } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { PulseText } from "@/components/pulse/pulse-text";
import { UserAvatar } from "@/components/pulse/user-avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import { haptics } from "@/lib/telegram";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { MediaItem, Pulse } from "@/types/api";

const MAX_LENGTH = 280;
const MAX_MEDIA = 4;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  replyTo?: Pulse;
  quoteOf?: Pulse;
  onPosted?: (pulse: Pulse) => void;
}

export function Composer({ open, onOpenChange, replyTo, quoteOf, onPosted }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [content, setContent] = React.useState("");
  const [media, setMedia] = React.useState<MediaItem[]>([]);
  const [uploading, setUploading] = React.useState(false);
  const fileInput = React.useRef<HTMLInputElement>(null);
  const textarea = React.useRef<HTMLTextAreaElement>(null);

  const remaining = MAX_LENGTH - content.length;
  const canPost = (content.trim().length > 0 || media.length > 0) && remaining >= 0;

  // Clear the draft as the dialog opens, adjusting state during render rather
  // than in an effect so there is no flash of the previous draft.
  const [wasOpen, setWasOpen] = React.useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setContent("");
      setMedia([]);
    }
  }

  React.useEffect(() => {
    if (!open) return;
    // Let the dialog finish animating before stealing focus, or mobile
    // keyboards open against a moving target.
    const timer = window.setTimeout(() => textarea.current?.focus(), 180);
    return () => window.clearTimeout(timer);
  }, [open]);

  const publish = useMutation({
    mutationFn: () =>
      api.createPulse({
        content: content.trim(),
        reply_to_id: replyTo?.id,
        quote_of_id: quoteOf?.id,
        media_ids: media.map((m) => m.id),
      }),
    onSuccess: (pulse) => {
      haptics.notify("success");
      toast.success(replyTo ? "Reply sent." : "Pulse sent.");
      onOpenChange(false);
      void queryClient.invalidateQueries();
      onPosted?.(pulse);
    },
    onError: (error) => {
      haptics.notify("error");
      toast.error(
        error instanceof ApiError ? error.message : "Could not post that. Try again.",
      );
    },
  });

  async function onPickFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []).slice(0, MAX_MEDIA - media.length);
    event.target.value = "";
    if (files.length === 0) return;

    setUploading(true);
    try {
      const uploaded = await Promise.all(files.map((file) => api.uploadImage(file)));
      setMedia((current) => [...current, ...uploaded].slice(0, MAX_MEDIA));
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "That image could not be uploaded.",
      );
    } finally {
      setUploading(false);
    }
  }

  const title = replyTo ? "Reply" : quoteOf ? "Quote pulse" : "New pulse";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[8%] max-h-[84dvh] translate-y-0 overflow-y-auto p-4" hideClose>
        <DialogHeader className="flex-row items-center justify-between space-y-0">
          <DialogTitle className="text-base">{title}</DialogTitle>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Cancel"
            className="rounded-full p-1.5 text-muted-foreground transition hover:bg-accent"
          >
            <X className="h-4 w-4" />
          </button>
        </DialogHeader>

        {replyTo ? (
          <div className="rounded-xl bg-secondary/60 p-3 text-sm">
            <p className="font-semibold">
              Replying to @{replyTo.author.username}
            </p>
            <PulseText
              text={replyTo.content}
              className="mt-1 line-clamp-3 text-[13px] text-muted-foreground"
            />
          </div>
        ) : null}

        <div className="flex gap-3">
          {user ? <UserAvatar user={user} linked={false} /> : null}
          <div className="min-w-0 flex-1">
            <Textarea
              ref={textarea}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder={replyTo ? "Post your reply" : "What's the pulse?"}
              rows={4}
              maxLength={MAX_LENGTH + 40}
              className="min-h-[110px] py-1"
            />

            {media.length > 0 ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                {media.map((item) => (
                  <div key={item.id} className="relative overflow-hidden rounded-xl">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={item.url}
                      alt={item.alt_text ?? ""}
                      className="aspect-square w-full object-cover"
                    />
                    <button
                      type="button"
                      aria-label="Remove image"
                      onClick={() =>
                        setMedia((current) => current.filter((m) => m.id !== item.id))
                      }
                      className="absolute right-1.5 top-1.5 rounded-full bg-black/65 p-1.5 text-white"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        {quoteOf ? (
          <div className="rounded-xl border border-border p-3 text-sm">
            <p className="font-semibold">{quoteOf.author.display_name}</p>
            <PulseText
              text={quoteOf.content}
              className="mt-0.5 line-clamp-3 text-[13px] text-muted-foreground"
            />
          </div>
        ) : null}

        <DialogFooter className="items-center justify-between">
          <div className="flex items-center gap-1">
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              multiple
              hidden
              onChange={onPickFiles}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Add image"
              disabled={uploading || media.length >= MAX_MEDIA}
              onClick={() => fileInput.current?.click()}
              className="text-primary"
            >
              {uploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ImagePlus className="h-[18px] w-[18px]" />
              )}
            </Button>
            <CharacterMeter remaining={remaining} />
          </div>

          <Button
            type="button"
            disabled={!canPost || publish.isPending}
            onClick={() => publish.mutate()}
          >
            {publish.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {replyTo ? "Reply" : "Pulse"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** A ring that fills as the pulse is written, turning red past the limit. */
function CharacterMeter({ remaining }: { remaining: number }) {
  const used = MAX_LENGTH - remaining;
  if (used === 0) return null;

  const ratio = Math.min(used / MAX_LENGTH, 1);
  const circumference = 2 * Math.PI * 9;
  const over = remaining < 0;
  const close = remaining <= 20;

  return (
    <div className="flex items-center gap-1.5">
      <svg viewBox="0 0 24 24" className="h-6 w-6 -rotate-90">
        <circle cx="12" cy="12" r="9" className="fill-none stroke-border" strokeWidth="2.5" />
        <circle
          cx="12"
          cy="12"
          r="9"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - ratio)}
          className={cn(
            "fill-none transition-all",
            over ? "stroke-destructive" : close ? "stroke-amber-500" : "stroke-primary",
          )}
        />
      </svg>
      {close ? (
        <span
          className={cn(
            "text-xs font-semibold tabular-nums",
            over ? "text-destructive" : "text-amber-500",
          )}
        >
          {remaining}
        </span>
      ) : null}
    </div>
  );
}
