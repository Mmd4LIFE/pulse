"use client";

/**
 * Like, repost, and bookmark, applied optimistically.
 *
 * A tap has to feel instant, so the cached pulse is updated before the request
 * goes out and rolled back if the server disagrees. Every cached list is
 * patched at once, because the same pulse can appear in the home feed, a
 * profile, a thread and search results simultaneously.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { haptics } from "@/lib/telegram";
import type { Page, Pulse, Thread } from "@/types/api";

type Interaction = "like" | "repulse" | "bookmark";

const COUNTER: Record<Interaction, keyof Pulse> = {
  like: "like_count",
  repulse: "repulse_count",
  bookmark: "bookmark_count",
};

const FLAG: Record<Interaction, keyof Pulse> = {
  like: "is_liked",
  repulse: "is_repulsed",
  bookmark: "is_bookmarked",
};

function applyToPulse(pulse: Pulse, id: number, kind: Interaction, on: boolean): Pulse {
  if (pulse.id !== id) return pulse;
  const flag = FLAG[kind] as "is_liked";
  const counter = COUNTER[kind] as "like_count";
  if (pulse[flag] === on) return pulse;
  return {
    ...pulse,
    [flag]: on,
    [counter]: Math.max(0, pulse[counter] + (on ? 1 : -1)),
  };
}

/** Walk every cached shape that can hold a pulse and rewrite the one that matches. */
function patchCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  id: number,
  kind: Interaction,
  on: boolean,
) {
  queryClient.setQueriesData<{ pages: Page<Pulse>[] } | Page<Pulse> | Pulse | Thread>(
    { predicate: () => true },
    (data) => {
      if (!data) return data;

      // Infinite feed
      if ("pages" in data && Array.isArray(data.pages)) {
        return {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            items: page.items.map((p) => applyToPulse(p, id, kind, on)),
          })),
        };
      }

      // Single page
      if ("items" in data && Array.isArray(data.items)) {
        return { ...data, items: data.items.map((p) => applyToPulse(p, id, kind, on)) };
      }

      // Thread
      if ("pulse" in data && "replies" in data) {
        const thread = data as Thread;
        return {
          ...thread,
          ancestors: thread.ancestors.map((p) => applyToPulse(p, id, kind, on)),
          pulse: applyToPulse(thread.pulse, id, kind, on),
          replies: thread.replies.map((p) => applyToPulse(p, id, kind, on)),
        };
      }

      // A lone pulse
      if ("id" in data && "author" in data) {
        return applyToPulse(data as Pulse, id, kind, on);
      }

      return data;
    },
  );
}

function useInteraction(kind: Interaction) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, on }: { id: number; on: boolean }) => {
      if (kind === "like") return on ? api.like(id) : api.unlike(id);
      if (kind === "repulse") return on ? api.repulse(id) : api.unrepulse(id);
      return on ? api.bookmark(id) : api.unbookmark(id);
    },
    onMutate: ({ id, on }) => {
      haptics.tap(on ? "medium" : "light");
      patchCaches(queryClient, id, kind, on);
      return { id, on };
    },
    onError: (_error, { id, on }) => {
      patchCaches(queryClient, id, kind, !on);
      toast.error("That did not go through. Try again.");
    },
  });
}

export function usePulseActions() {
  // Three fixed calls in a fixed order, so this stays a legal hook composition.
  return {
    like: useInteraction("like"),
    repulse: useInteraction("repulse"),
    bookmark: useInteraction("bookmark"),
  };
}

export function useDeletePulse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deletePulse(id),
    onSuccess: () => {
      haptics.notify("success");
      toast.success("Pulse deleted.");
      void queryClient.invalidateQueries();
    },
    onError: () => toast.error("Could not delete that pulse."),
  });
}

export function useFollow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ username, on }: { username: string; on: boolean }) =>
      on ? api.follow(username) : api.unfollow(username),
    onMutate: ({ on }) => haptics.tap(on ? "medium" : "light"),
    onSuccess: () => void queryClient.invalidateQueries(),
    onError: () => toast.error("Could not update that follow."),
  });
}
