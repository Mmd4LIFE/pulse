"use client";

import { Hash } from "lucide-react";
import { useParams } from "next/navigation";

import { AppFrame } from "@/components/layout/app-frame";
import { PageHeader } from "@/components/layout/page-header";
import { PulseList } from "@/components/pulse/pulse-list";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";

export default function HashtagPage() {
  const params = useParams<{ tag: string }>();
  const tag = decodeURIComponent(params.tag ?? "");

  const feed = useInfiniteFeed(["feed", "tag", tag], (page) => api.hashtagFeed(tag, page), {
    enabled: Boolean(tag),
  });

  return (
    <AppFrame header={<PageHeader title={`#${tag}`} showBack />}>
      <PulseList
        items={feed.items}
        isLoading={feed.isLoading}
        isError={feed.isError}
        hasNextPage={feed.hasNextPage}
        isFetchingNextPage={feed.isFetchingNextPage}
        fetchNextPage={feed.fetchNextPage}
        refetch={feed.refetch}
        emptyIcon={<Hash className="h-10 w-10" />}
        emptyTitle={`Nothing tagged #${tag}`}
        emptyHint="Post the first one."
      />
    </AppFrame>
  );
}
