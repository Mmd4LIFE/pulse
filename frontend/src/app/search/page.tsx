"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { AppFrame } from "@/components/layout/app-frame";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { PulseCard } from "@/components/pulse/pulse-card";
import { PulseSkeleton } from "@/components/pulse/pulse-skeleton";
import { UserRow } from "@/components/pulse/user-row";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { compactNumber } from "@/lib/utils";

function SearchScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const query = params.get("q") ?? "";
  const [term, setTerm] = React.useState(query);
  const [syncedQuery, setSyncedQuery] = React.useState(query);

  // Navigating to a new ?q= re-seeds the box. Adjusting during render is the
  // supported way to derive state from a changing prop without an extra pass.
  if (query !== syncedQuery) {
    setSyncedQuery(query);
    setTerm(query);
  }

  const results = useQuery({
    queryKey: ["search", query],
    queryFn: () => api.search(query),
    enabled: query.trim().length > 0,
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const next = term.trim();
    if (next) router.replace(`/search?q=${encodeURIComponent(next)}`);
  };

  return (
    <AppFrame
      hideCompose
      header={
        <PageHeader title="Search" showBack>
          <form onSubmit={submit} className="px-4 pb-3">
            <div className="relative">
              <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                autoFocus={!query}
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                placeholder="Search people, pulses, tags"
                className="pl-10"
                type="search"
                enterKeyHint="search"
              />
            </div>
          </form>
        </PageHeader>
      }
    >
      {!query ? (
        <EmptyState
          icon={<Search className="h-10 w-10" />}
          title="Search Pulse"
          hint="Find people, pulses and hashtags."
        />
      ) : results.isLoading ? (
        <div>
          <PulseSkeleton />
          <PulseSkeleton />
          <PulseSkeleton />
        </div>
      ) : (
        <Tabs defaultValue="top">
          <TabsList>
            <TabsTrigger value="top">Top</TabsTrigger>
            <TabsTrigger value="people">People</TabsTrigger>
            <TabsTrigger value="tags">Tags</TabsTrigger>
          </TabsList>

          <TabsContent value="top">
            {results.data?.pulses.length ? (
              results.data.pulses.map((pulse) => (
                <PulseCard key={pulse.id} pulse={pulse} />
              ))
            ) : (
              <EmptyState
                title={`No pulses for "${query}"`}
                hint="Try a different word."
              />
            )}
          </TabsContent>

          <TabsContent value="people">
            {results.data?.users.length ? (
              results.data.users.map((user) => <UserRow key={user.id} user={user} />)
            ) : (
              <EmptyState title="No accounts found" />
            )}
          </TabsContent>

          <TabsContent value="tags">
            {results.data?.hashtags.length ? (
              <ul>
                {results.data.hashtags.map((tag) => (
                  <li key={tag.tag}>
                    <Link
                      href={`/tag/${encodeURIComponent(tag.tag)}`}
                      className="block border-b border-border px-4 py-3.5 transition-colors hover:bg-accent/40"
                    >
                      <span className="block font-bold">#{tag.tag}</span>
                      <span className="text-xs text-muted-foreground">
                        {compactNumber(tag.usage_count)} uses
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No hashtags found" />
            )}
          </TabsContent>
        </Tabs>
      )}
    </AppFrame>
  );
}

export default function SearchPage() {
  // useSearchParams needs a Suspense boundary during prerender.
  return (
    <React.Suspense fallback={null}>
      <SearchScreen />
    </React.Suspense>
  );
}
