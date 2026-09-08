"use client";

/** Explore: search, trends, suggested accounts, and the public firehose. */

import { useQuery } from "@tanstack/react-query";
import { Search, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { AppFrame } from "@/components/layout/app-frame";
import { PageHeader } from "@/components/layout/page-header";
import { PulseList } from "@/components/pulse/pulse-list";
import { UserRow } from "@/components/pulse/user-row";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";
import { compactNumber } from "@/lib/utils";

export default function ExplorePage() {
  const router = useRouter();
  const [term, setTerm] = React.useState("");

  const feed = useInfiniteFeed(["feed", "explore"], (params) => api.exploreFeed(params));
  const trends = useQuery({ queryKey: ["trends"], queryFn: () => api.trends(10) });
  const suggestions = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => api.suggestions(8),
  });

  const onSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const query = term.trim();
    if (query) router.push(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <AppFrame
      header={
        <PageHeader title="Explore">
          <form onSubmit={onSearch} className="px-4 pb-3">
            <div className="relative">
              <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                placeholder="Search Pulse"
                className="pl-10"
                enterKeyHint="search"
                type="search"
              />
            </div>
          </form>
        </PageHeader>
      }
    >
      <Tabs defaultValue="latest">
        <TabsList>
          <TabsTrigger value="latest">Latest</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
          <TabsTrigger value="people">People</TabsTrigger>
        </TabsList>

        <TabsContent value="latest">
          <PulseList
            items={feed.items}
            isLoading={feed.isLoading}
            isError={feed.isError}
            hasNextPage={feed.hasNextPage}
            isFetchingNextPage={feed.isFetchingNextPage}
            fetchNextPage={feed.fetchNextPage}
            refetch={feed.refetch}
            emptyTitle="No pulses yet"
            emptyHint="Be the first to say something."
          />
        </TabsContent>

        <TabsContent value="trends">
          {trends.data && trends.data.length > 0 ? (
            <ul>
              {trends.data.map((trend) => (
                <li key={trend.tag}>
                  <Link
                    href={`/tag/${encodeURIComponent(trend.tag)}`}
                    className="flex items-center gap-3 border-b border-border px-4 py-3.5 transition-colors hover:bg-accent/40"
                  >
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary text-muted-foreground">
                      <TrendingUp className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-bold">#{trend.tag}</span>
                      <span className="block text-xs text-muted-foreground">
                        {compactNumber(trend.pulse_count)}{" "}
                        {trend.pulse_count === 1 ? "pulse" : "pulses"}
                      </span>
                    </span>
                    <span className="text-sm font-semibold text-muted-foreground">
                      #{trend.rank}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-4 py-16 text-center text-sm text-muted-foreground">
              Nothing is trending yet. Start a hashtag.
            </p>
          )}
        </TabsContent>

        <TabsContent value="people">
          {suggestions.data?.length ? (
            suggestions.data.map((user) => <UserRow key={user.id} user={user} />)
          ) : (
            <p className="px-4 py-16 text-center text-sm text-muted-foreground">
              No suggestions right now.
            </p>
          )}
        </TabsContent>
      </Tabs>
    </AppFrame>
  );
}
