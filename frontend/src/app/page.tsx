"use client";

/** Home: the timeline of everyone you follow. */

import { Sparkles } from "lucide-react";
import Link from "next/link";

import { AppFrame } from "@/components/layout/app-frame";
import { PageHeader } from "@/components/layout/page-header";
import { PulseMark } from "@/components/layout/pulse-mark";
import { PulseList } from "@/components/pulse/pulse-list";
import { Button } from "@/components/ui/button";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";

export default function HomePage() {
  const feed = useInfiniteFeed(["feed", "home"], (params) => api.homeFeed(params));

  return (
    <AppFrame
      header={
        <PageHeader
          title={
            <span className="flex items-center gap-2">
              <PulseMark className="h-6 w-6 text-primary" />
              Pulse
            </span>
          }
        />
      }
    >
      <PulseList
        items={feed.items}
        isLoading={feed.isLoading}
        isError={feed.isError}
        hasNextPage={feed.hasNextPage}
        isFetchingNextPage={feed.isFetchingNextPage}
        fetchNextPage={feed.fetchNextPage}
        refetch={feed.refetch}
        emptyIcon={<Sparkles className="h-10 w-10" />}
        emptyTitle="Your feed is quiet"
        emptyHint="Follow a few people and their pulses will land here."
      />
      {!feed.isLoading && feed.items.length === 0 ? (
        <div className="flex justify-center pb-10">
          <Button asChild variant="outline">
            <Link href="/explore">Find people to follow</Link>
          </Button>
        </div>
      ) : null}
    </AppFrame>
  );
}
