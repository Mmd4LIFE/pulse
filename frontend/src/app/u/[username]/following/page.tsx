"use client";

import { useParams } from "next/navigation";

import { AppFrame } from "@/components/layout/app-frame";
import { PageHeader } from "@/components/layout/page-header";
import { PeopleList } from "@/components/pulse/people-list";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";

export default function FollowingPage() {
  const params = useParams<{ username: string }>();
  const username = decodeURIComponent(params.username ?? "");

  const feed = useInfiniteFeed(
    ["user", username, "following"],
    (page) => api.following(username, page),
    { enabled: Boolean(username) },
  );

  return (
    <AppFrame
      hideCompose
      header={<PageHeader title="Following" subtitle={`@${username}`} showBack />}
    >
      <PeopleList
        items={feed.items}
        isLoading={feed.isLoading}
        hasNextPage={feed.hasNextPage}
        isFetchingNextPage={feed.isFetchingNextPage}
        fetchNextPage={feed.fetchNextPage}
        emptyTitle="Nobody here yet"
      />
    </AppFrame>
  );
}
