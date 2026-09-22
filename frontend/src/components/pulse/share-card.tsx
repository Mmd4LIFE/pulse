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
import { formatScore } from "@/components/pulse/pulse-score";
import { api } from "@/lib/api";
import { detectDirection } from "@/lib/direction";
import { avatarTone, cn, fullTimestamp, initials } from "@/lib/utils";
import type { Pulse } from "@/types/api";

/** CSS pixels. Doubled on export, which stays inside Telegram's photo limits. */
export const CARD_WIDTH = 600;

const BACKDROP = "#f2f4f8";
/** Drawn at twice the layout size, which stays inside Telegram's photo limits. */
const SCALE = 2;

export const ShareCard = React.forwardRef<
  HTMLDivElement,
  { pulse: Pulse; avatar?: string | null }
>(function ShareCard({ pulse, avatar }, ref) {
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
              "relative flex h-[56px] w-[56px] shrink-0 items-center justify-center overflow-hidden rounded-full text-[20px] font-bold text-white",
              avatarTone(author.username),
            )}
          >
            {/*
              The initials are underneath rather than instead of the photo, so
              that a photo which fails to draw leaves a name behind instead of
              an empty disc.
            */}
            {initials(author.display_name)}
            {avatar ? (
              // Already a data URL by the time it gets here: Telegram's own
              // copy is unreadable to a canvas, so it is fetched through the
              // app's origin and inlined before the card is photographed.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatar}
                alt=""
                width={56}
                height={56}
                className="absolute inset-0 h-full w-full rounded-full object-cover"
              />
            ) : null}
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

        {pulse.score === null ? null : (
          // The score and nothing else. Likes and reposts say how a pulse did
          // here; a picture sent to someone who has never opened Pulse should
          // carry what it says about the writing instead.
          <div className="mt-4 flex items-baseline gap-3 border-t border-[#e6eaf0] pt-4">
            <span className="flex items-baseline gap-1 text-[#0f1419]">
              <span className="text-[34px] font-bold leading-none tabular-nums">
                {formatScore(pulse.score)}
              </span>
              <span className="text-[17px] font-semibold text-[#5b6b7c]">
                /10
              </span>
            </span>
            <span className="text-[14px] font-semibold uppercase tracking-[0.1em] text-[#5b6b7c]">
              Pulse Score
            </span>
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-center gap-2 text-[15px] font-semibold text-[#5b6b7c]">
        <PulseMark className="h-5 w-5 text-[#2563eb]" />
        <span>Pulse</span>
      </div>
    </div>
  );
});

/**
 * Fetch an account's photo as a data URL, or nothing if it has none.
 *
 * Inlining it up front is what makes the snapshot deterministic: by the time
 * the card is photographed the picture is part of the document, not a request
 * that may or may not have landed.
 */
export async function loadAvatar(username: string): Promise<string | null> {
  try {
    const response = await fetch(api.avatarSource(username));
    if (!response.ok) return null;
    const blob = await response.blob();
    return await new Promise<string | null>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

/**
 * Snapshot a rendered card as a JPEG, which is the only format Telegram takes.
 *
 * The snapshot works by cloning the card into an SVG foreignObject and drawing
 * that to a canvas. Pictures inside such a clone are unreliable: the WebView
 * Telegram uses drops them often enough that a shared card came back with an
 * empty circle where a profile photo should be, while the same code in desktop
 * Chrome drew it every time.
 *
 * So every picture is painted onto the canvas again here, from the images the
 * page has already loaded, over whatever the snapshot did or did not manage.
 * Drawing the same picture twice costs nothing and settles the question.
 *
 * They are painted over rather than left out: leaving a picture out of the
 * snapshot collapses the space it occupied, and everything below it moves up.
 */
export async function renderShareCard(node: HTMLElement): Promise<Blob> {
  const pictures = Array.from(node.querySelectorAll("img"));
  await Promise.all(pictures.map((img) => img.decode().catch(() => undefined)));

  const width = CARD_WIDTH;
  const height = node.offsetHeight;

  const base = await toJpeg(node, {
    quality: 0.94,
    pixelRatio: SCALE,
    backgroundColor: BACKDROP,
    width,
    height,
  });

  const canvas = document.createElement("canvas");
  canvas.width = width * SCALE;
  canvas.height = height * SCALE;
  const context = canvas.getContext("2d");
  if (!context) return asBlob(base);

  context.drawImage(await asImage(base), 0, 0, canvas.width, canvas.height);

  const card = node.getBoundingClientRect();
  for (const picture of pictures) {
    // A picture that never loaded has nothing to paint, and whatever is
    // underneath it -- the initials on an avatar -- is already in the snapshot.
    if (!picture.naturalWidth) continue;
    paint(context, picture, picture.getBoundingClientRect(), card);
  }

  return asBlob(canvas.toDataURL("image/jpeg", 0.94));
}

/** Draw one picture where the layout put it, cropped and rounded as it is. */
function paint(
  context: CanvasRenderingContext2D,
  picture: HTMLImageElement,
  box: DOMRect,
  card: DOMRect,
): void {
  const x = (box.left - card.left) * SCALE;
  const y = (box.top - card.top) * SCALE;
  const width = box.width * SCALE;
  const height = box.height * SCALE;

  context.save();
  clipRounded(context, x, y, width, height, cornerRadius(picture, box));

  // object-fit: cover, by hand: fill the box with the middle of the picture
  // rather than squashing it into a different shape.
  const scale = Math.max(
    width / picture.naturalWidth,
    height / picture.naturalHeight,
  );
  const drawn = {
    w: picture.naturalWidth * scale,
    h: picture.naturalHeight * scale,
  };
  context.drawImage(
    picture,
    x + (width - drawn.w) / 2,
    y + (height - drawn.h) / 2,
    drawn.w,
    drawn.h,
  );
  context.restore();
}

function cornerRadius(picture: HTMLImageElement, box: DOMRect): number {
  const declared = getComputedStyle(picture).borderTopLeftRadius;
  const value = declared.endsWith("%")
    ? (parseFloat(declared) / 100) * box.width
    : parseFloat(declared) || 0;
  // A "fully round" radius is written as something enormous; cap it at what
  // the box can actually take.
  return Math.min(value, box.width / 2, box.height / 2) * SCALE;
}

function clipRounded(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
  context.clip();
}

function asImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () =>
      reject(new Error("the snapshot could not be read back"));
    image.src = dataUrl;
  });
}

async function asBlob(dataUrl: string): Promise<Blob> {
  return (await fetch(dataUrl)).blob();
}
