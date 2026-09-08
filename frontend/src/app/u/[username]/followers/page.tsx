"use client";

import { useParams } from "next/navigation";

import { AppFrame } from "@/components/layout/app-frame";
import { PageHeader } from "@/components/layout/page-header";
import { PeopleList } from "@/components/pulse/people-list";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";

export default function FollowersPage() {
  const params = useParams<{ username: string }>();
  const username = decodeURIComponent(params.username ?? "");

  const feed = useInfiniteFeed(
    ["user", username, "followers"],
    (page) => api.followers(username, page),
    { enabled: Boolean(username) },
  );

  return (
    <AppFrame
      hideCompose
      header={<PageHeader title="Followers" subtitle={`@${username}`} showBack />}
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
