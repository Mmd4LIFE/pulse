"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2, Type } from "lucide-react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { haptics } from "@/lib/telegram";
import { TEXT_SIZES, type TextSize, applyTextSize } from "@/lib/text-size";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";

export function TextSizeCard() {
  const { user, setUser } = useAuth();

  const save = useMutation({
    mutationFn: (size: TextSize) => api.setTextSize(size),
    onSuccess: (updated) => setUser(updated),
    onError: (error, _size, context) => {
      // Put the preview back to whatever is actually stored.
      if (context) applyTextSize(context as TextSize);
      toast.error(
        error instanceof ApiError ? error.message : "Could not save that size.",
      );
    },
    onMutate: (size) => {
      const previous = user?.text_size ?? "small";
      // Applied before the request so the change is instant; rolled back above
      // if the server disagrees.
      applyTextSize(size);
      haptics.select();
      return previous;
    },
  });

  if (!user) return null;
  const current = user.text_size;

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Text size</h2>

      <div className="space-y-3 rounded-xl border border-border p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-secondary text-muted-foreground">
            <Type className="h-5 w-5" />
          </span>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Sets how large pulses and profiles read. It follows your account, so
            it is the same on every device you open Pulse on.
          </p>
        </div>

        <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label="Text size">
          {TEXT_SIZES.map((size) => (
            <button
              key={size.value}
              type="button"
              role="radio"
              aria-checked={current === size.value}
              disabled={save.isPending}
              onClick={() => {
                if (size.value !== current) save.mutate(size.value);
              }}
              className={cn(
                "flex flex-col items-center gap-1 rounded-xl border px-1 py-2.5 transition-colors",
                current === size.value
                  ? "border-primary bg-primary/10"
                  : "border-border hover:bg-accent/40",
              )}
            >
              {/* Fixed px, so each swatch previews its own size rather than
                  being resized by the setting it represents. */}
              <span
                aria-hidden
                className="font-bold leading-none"
                style={{ fontSize: `${Math.round(size.scale * 16)}px` }}
              >
                A
              </span>
              <span className="text-2xs leading-none text-muted-foreground">
                {size.label}
              </span>
            </button>
          ))}
        </div>

        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          {save.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          The quick brown fox jumps over the lazy dog.
        </p>
      </div>
    </section>
  );
}
