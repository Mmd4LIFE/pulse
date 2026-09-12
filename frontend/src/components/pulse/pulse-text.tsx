"use client";

/**
 * Renders pulse text with hashtags, @mentions and links made interactive.
 *
 * The text is split on a single pass over the source string and every segment
 * is emitted as its own node, so nothing is ever injected as raw HTML.
 */

import Link from "next/link";
import * as React from "react";

import { detectDirection } from "@/lib/direction";
import { openExternal } from "@/lib/telegram";
import { cn } from "@/lib/utils";

const ENTITY_RE =
  /(https?:\/\/[^\s<>"]+)|(?<![\w&/])#([A-Za-z؀-ۿ][\w؀-ۿ]{0,63})|(?<![\w/])@([A-Za-z0-9_]{3,32})(?!\w)/g;

interface Segment {
  key: string;
  node: React.ReactNode;
}

export function PulseText({ text, className }: { text: string; className?: string }) {
  const segments = React.useMemo(() => parse(text), [text]);
  const direction = React.useMemo(() => detectDirection(text), [text]);

  if (!text) return null;

  return (
    <p
      dir={direction}
      className={cn(
        // text-start rather than text-left, so alignment follows the direction.
        "whitespace-pre-wrap break-anywhere text-start text-base",
        className,
      )}
    >
      {segments.map((segment) => (
        <React.Fragment key={segment.key}>{segment.node}</React.Fragment>
      ))}
    </p>
  );
}

function parse(text: string): Segment[] {
  const out: Segment[] = [];
  let lastIndex = 0;
  let index = 0;

  for (const match of text.matchAll(ENTITY_RE)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      out.push({ key: `t${index++}`, node: text.slice(lastIndex, start) });
    }

    const [whole, url, hashtag, mention] = match;

    if (url) {
      out.push({
        key: `u${index++}`,
        node: (
          <bdi>
            <a
              href={url}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                openExternal(url);
              }}
              className="entity-link"
            >
              {prettyUrl(url)}
            </a>
          </bdi>
        ),
      });
    } else if (hashtag) {
      out.push({
        key: `h${index++}`,
        node: (
          <bdi>
            <Link
              href={`/tag/${encodeURIComponent(hashtag.toLowerCase())}`}
              onClick={(event) => event.stopPropagation()}
              className="entity-link"
            >
              #{hashtag}
            </Link>
          </bdi>
        ),
      });
    } else if (mention) {
      out.push({
        key: `m${index++}`,
        node: (
          <bdi>
            <Link
              href={`/u/${mention}`}
              onClick={(event) => event.stopPropagation()}
              className="entity-link"
            >
              @{mention}
            </Link>
          </bdi>
        ),
      });
    } else {
      out.push({ key: `x${index++}`, node: whole });
    }

    lastIndex = start + whole.length;
  }

  if (lastIndex < text.length) {
    out.push({ key: `t${index++}`, node: text.slice(lastIndex) });
  }
  return out;
}

/** Show "example.com/path" rather than the full scheme-and-query mouthful. */
function prettyUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const shown = `${parsed.hostname.replace(/^www\./, "")}${parsed.pathname}`.replace(
      /\/$/,
      "",
    );
    return shown.length > 32 ? `${shown.slice(0, 32)}…` : shown;
  } catch {
    return url;
  }
}
