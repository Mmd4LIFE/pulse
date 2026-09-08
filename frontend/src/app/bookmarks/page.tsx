"use client";

import { Bookmark } from "lucide-react";

import { AppFrame } from "@/components/layout/app-frame";
import { PageHeader } from "@/components/layout/page-header";
import { PulseList } from "@/components/pulse/pulse-list";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";

export default function BookmarksPage() {
  const feed = useInfiniteFeed(["feed", "bookmarks"], (params) => api.bookmarks(params));

  return (
    <AppFrame header={<PageHeader title="Bookmarks" subtitle="Only you can see these" />}>
      <PulseList
        items={feed.items}
        isLoading={feed.isLoading}
        isError={feed.isError}
        hasNextPage={feed.hasNextPage}
        isFetchingNextPage={feed.isFetchingNextPage}
        fetchNextPage={feed.fetchNextPage}
        refetch={feed.refetch}
        emptyIcon={<Bookmark className="h-10 w-10" />}
        emptyTitle="No bookmarks yet"
        emptyHint="Tap the bookmark icon on a pulse to keep it here."
      />
    </AppFrame>
  );
}
