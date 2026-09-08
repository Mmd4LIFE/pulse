"use client";

import { Loader2 } from "lucide-react";

import { EmptyState } from "@/components/layout/empty-state";
import { UserRow } from "@/components/pulse/user-row";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { UserPublic } from "@/types/api";

interface Props {
  items: UserPublic[];
  isLoading: boolean;
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
  fetchNextPage?: () => void;
  emptyTitle: string;
}

export function PeopleList({
  items,
  isLoading,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  emptyTitle,
}: Props) {
  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="flex gap-3">
            <Skeleton className="h-11 w-11 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3.5 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) return <EmptyState title={emptyTitle} />;

  return (
    <div>
      {items.map((user) => (
        <UserRow key={user.id} user={user} />
      ))}
      {hasNextPage ? (
        <div className="flex justify-center py-6">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchNextPage}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Load more
          </Button>
        </div>
      ) : null}
    </div>
  );
}
