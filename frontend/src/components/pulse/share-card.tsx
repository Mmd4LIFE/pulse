"use client";

/**
 * The picture of a pulse that gets shared into a Telegram chat.
 *
 * It is drawn in the browser rather than on the server, because everything a
 * faithful picture needs is already here: the app's fonts, its colours, and a
 * text engine that lays Persian and Arabic out correctly. The node is rendered
 * off-screen and snapshotted.
 *
 * Sizes are given in fixed pixels instead of the app's type scale, so the
 * picture looks the same whatever font size the reader has chosen for
 * themselves -- their setting is about reading, not about what they send out.
 */

import { toJpeg } from "html-to-image";
import * as React from "react";

import { PulseMark } from "@/components/layout/pulse-mark";
import { detectDirection } from "@/lib/direction";
import {
  avatarTone,
  cn,
  compactNumber,
  fullTimestamp,
  initials,
} from "@/lib/utils";
import type { Pulse } from "@/types/api";

/** CSS pixels. Doubled on export, which stays inside Telegram's photo limits. */
export const CARD_WIDTH = 600;

const BACKDROP = "#f2f4f8";

export const ShareCard = React.forwardRef<HTMLDivElement, { pulse: Pulse }>(
  function ShareCard({ pulse }, ref) {
    const { author } = pulse;
    const direction = detectDirection(pulse.content);
    const photo = pulse.media[0];

    return (
      <div
        ref={ref}
        style={{ width: CARD_WIDTH, backgroundColor: BACKDROP }}
        className="p-7 font-sans"
      >
        <div className="rounded-[28px] bg-white p-7 shadow-[0_10px_40px_-16px_rgba(20,30,60,0.25)]">
          <div className="flex items-center gap-3.5">
            <div
              className={cn(
                "flex h-[56px] w-[56px] shrink-0 items-center justify-center rounded-full text-[20px] font-bold text-white",
                // The account's own photo lives on Telegram's CDN, which will
                // not hand it to a canvas. Initials are what the app shows for
                // everyone without a photo anyway, so the card uses them for
                // everyone and stays consistent instead of half-blank.
                avatarTone(author.username),
              )}
            >
              {initials(author.display_name)}
            </div>
            <div className="min-w-0">
              <p className="truncate text-[19px] font-bold leading-tight text-[#0f1419]">
                {author.display_name}
              </p>
              <p className="truncate text-[15px] leading-tight text-[#5b6b7c]">
                @{author.username}
              </p>
            </div>
          </div>

          <p
            dir={direction}
            className={cn(
              "mt-5 whitespace-pre-wrap break-anywhere text-start text-[22px] text-[#0f1419]",
              direction === "rtl" ? "leading-[1.75]" : "leading-[1.45]",
            )}
          >
            {pulse.content}
          </p>

          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photo.url}
              alt=""
              className="mt-5 h-[300px] w-full rounded-[20px] object-cover"
            />
          ) : null}

          <p className="mt-5 text-[15px] text-[#5b6b7c]">
            {fullTimestamp(pulse.created_at)}
          </p>

          <div className="mt-4 flex items-center gap-5 border-t border-[#e6eaf0] pt-4 text-[15px] text-[#5b6b7c]">
            <Stat value={pulse.reply_count} one="reply" many="replies" />
            <Stat value={pulse.repulse_count} one="repulse" many="repulses" />
            <Stat value={pulse.like_count} one="like" many="likes" />
          </div>
        </div>

        <div className="mt-4 flex items-center justify-center gap-2 text-[15px] font-semibold text-[#5b6b7c]">
          <PulseMark className="h-5 w-5 text-[#2563eb]" />
          <span>Pulse</span>
        </div>
      </div>
    );
  },
);

function Stat({
  value,
  one,
  many,
}: {
  value: number;
  one: string;
  many: string;
}) {
  return (
    <span>
      <span className="font-bold text-[#0f1419]">{compactNumber(value)}</span>{" "}
      {value === 1 ? one : many}
    </span>
  );
}

/** Snapshot a rendered card as a JPEG, which is the only format Telegram takes. */
export async function renderShareCard(node: HTMLElement): Promise<Blob> {
  const dataUrl = await toJpeg(node, {
    quality: 0.94,
    pixelRatio: 2,
    backgroundColor: BACKDROP,
    width: CARD_WIDTH,
    height: node.offsetHeight,
  });
  const response = await fetch(dataUrl);
  return response.blob();
}
