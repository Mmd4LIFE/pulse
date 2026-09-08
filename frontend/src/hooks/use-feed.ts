"use client";

/** Infinite, cursor-paged timelines on top of TanStack Query. */

import { useInfiniteQuery } from "@tanstack/react-query";
import * as React from "react";

import type { PageQuery } from "@/lib/api";
import type { Page, Pulse, UserPublic } from "@/types/api";

type PageFetcher<T> = (params: PageQuery) => Promise<Page<T>>;

export function useInfiniteFeed<T>(
  key: readonly unknown[],
  fetchPage: PageFetcher<T>,
  options: { enabled?: boolean; limit?: number } = {},
) {
  const { enabled = true, limit = 20 } = options;

  const query = useInfiniteQuery({
    queryKey: key,
    enabled,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => fetchPage({ cursor: pageParam, limit }),
    getNextPageParam: (last) => last.next_cursor,
  });

  const items = React.useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data],
  );

  return { ...query, items };
}

export type PulseFeed = ReturnType<typeof useInfiniteFeed<Pulse>>;
export type UserFeed = ReturnType<typeof useInfiniteFeed<UserPublic>>;
