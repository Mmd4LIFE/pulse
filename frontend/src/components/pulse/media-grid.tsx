"use client";

/* eslint-disable @next/next/no-img-element */

import * as React from "react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { MediaItem } from "@/types/api";

/** Up to four images, laid out the way a timeline expects. */
export function MediaGrid({ media }: { media: MediaItem[] }) {
  const [openIndex, setOpenIndex] = React.useState<number | null>(null);

  if (media.length === 0) return null;

  const layout =
    media.length === 1
      ? "grid-cols-1"
      : media.length === 2
        ? "grid-cols-2"
        : "grid-cols-2 grid-rows-2";

  return (
    <>
      <div
        className={cn(
          "mt-3 grid gap-0.5 overflow-hidden rounded-2xl border border-border",
          layout,
        )}
      >
        {media.map((item, index) => (
          <button
            key={item.id}
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setOpenIndex(index);
            }}
            className={cn(
              "relative block overflow-hidden bg-muted",
              media.length === 1 ? "max-h-[420px]" : "aspect-square",
              // A third image spans the bottom row.
              media.length === 3 && index === 0 && "row-span-2",
            )}
          >
            <img
              src={item.url}
              alt={item.alt_text ?? ""}
              loading="lazy"
              className={cn(
                "h-full w-full",
                media.length === 1 ? "object-contain" : "object-cover",
              )}
            />
          </button>
        ))}
      </div>

      <Dialog
        open={openIndex !== null}
        onOpenChange={(open) => !open && setOpenIndex(null)}
      >
        <DialogContent className="max-w-3xl border-none bg-transparent p-0 shadow-none">
          <DialogTitle className="sr-only">Image</DialogTitle>
          {openIndex !== null && media[openIndex] ? (
            <img
              src={media[openIndex]!.url}
              alt={media[openIndex]!.alt_text ?? ""}
              className="max-h-[85dvh] w-full rounded-xl object-contain"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
