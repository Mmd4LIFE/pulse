"use client";

/** Renders a paged timeline, loading the next page as it scrolls into view. */

import { Loader2 } from "lucide-react";
import * as React from "react";

import { PulseCard } from "@/components/pulse/pulse-card";
import { PulseSkeleton } from "@/components/pulse/pulse-skeleton";
import { EmptyState } from "@/components/layout/empty-state";
import { Button } from "@/components/ui/button";
import type { Pulse } from "@/types/api";

interface Props {
  items: Pulse[];
  isLoading: boolean;
  isError?: boolean;
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
  fetchNextPage?: () => void;
  refetch?: () => void;
  emptyTitle?: string;
  emptyHint?: string;
  emptyIcon?: React.ReactNode;
}

export function PulseList({
  items,
  isLoading,
  isError,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  refetch,
  emptyTitle = "Nothing here yet",
  emptyHint,
  emptyIcon,
}: Props) {
  const sentinel = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNextPage || !fetchNextPage) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isFetchingNextPage) fetchNextPage();
      },
      // Start fetching before the sentinel is actually visible.
      { rootMargin: "600px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, fetchNextPage, isFetchingNextPage]);

  if (isLoading) {
    return (
      <div>
        {Array.from({ length: 5 }).map((_, index) => (
          <PulseSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <EmptyState
        title="Could not load this feed"
        hint="Something went wrong on the way. Give it another go."
        action={
          refetch ? (
            <Button variant="outline" onClick={refetch}>
              Retry
            </Button>
          ) : undefined
        }
      />
    );
  }

  if (items.length === 0) {
    return <EmptyState title={emptyTitle} hint={emptyHint} icon={emptyIcon} />;
  }

  return (
    <div>
      {items.map((pulse, index) => (
        <PulseCard
          key={`${pulse.id}-${pulse.repulsed_by?.id ?? "own"}-${index}`}
          pulse={pulse}
          className="animate-fade-up"
        />
      ))}

      <div ref={sentinel} className="flex justify-center py-8">
        {isFetchingNextPage ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        ) : !hasNextPage && items.length > 6 ? (
          <p className="text-xs text-muted-foreground">You are all caught up.</p>
        ) : null}
      </div>
    </div>
  );
}
