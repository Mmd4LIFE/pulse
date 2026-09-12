"use client";

/** A single pulse with the conversation above and below it. */

import { useQuery } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { useParams } from "next/navigation";
import * as React from "react";

import { AppFrame } from "@/components/layout/app-frame";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Composer } from "@/components/pulse/composer";
import { PulseCard } from "@/components/pulse/pulse-card";
import { PulseSkeleton } from "@/components/pulse/pulse-skeleton";
import { UserAvatar } from "@/components/pulse/user-avatar";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { compactNumber } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";

export default function ThreadPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const { user } = useAuth();
  const [replying, setReplying] = React.useState(false);

  const thread = useQuery({
    queryKey: ["thread", id],
    queryFn: () => api.getThread(id, { limit: 30 }),
    enabled: Number.isFinite(id) && id > 0,
  });

  if (thread.isLoading) {
    return (
      <AppFrame hideCompose header={<PageHeader title="Pulse" showBack />}>
        <PulseSkeleton />
        <PulseSkeleton />
      </AppFrame>
    );
  }

  if (thread.isError || !thread.data) {
    return (
      <AppFrame hideCompose header={<PageHeader title="Pulse" showBack />}>
        <EmptyState
          title="This pulse is gone"
          hint="It may have been deleted, or the link is wrong."
        />
      </AppFrame>
    );
  }

  const { ancestors, pulse, replies } = thread.data;

  return (
    <AppFrame hideCompose header={<PageHeader title="Pulse" showBack />}>
      {ancestors.map((ancestor) => (
        <PulseCard key={ancestor.id} pulse={ancestor} connected />
      ))}

      <PulseCard pulse={pulse} variant="detail" />

      <EngagementBar pulse={pulse} />

      <button
        type="button"
        onClick={() => setReplying(true)}
        className="flex w-full items-center gap-3 border-b border-border px-4 py-3.5 text-left transition-colors hover:bg-accent/40"
      >
        {user ? <UserAvatar user={user} className="h-9 w-9" linked={false} /> : null}
        <span className="text-base text-muted-foreground">
          Reply to @{pulse.author.username}
        </span>
      </button>

      {replies.length > 0 ? (
        replies.map((reply) => <PulseCard key={reply.id} pulse={reply} />)
      ) : (
        <EmptyState
          icon={<MessageCircle className="h-9 w-9" />}
          title="No replies yet"
          hint="Start the conversation."
          action={
            <Button variant="outline" onClick={() => setReplying(true)}>
              Write a reply
            </Button>
          }
        />
      )}

      <Composer
        open={replying}
        onOpenChange={setReplying}
        replyTo={pulse}
        onPosted={() => thread.refetch()}
      />
    </AppFrame>
  );
}

function EngagementBar({
  pulse,
}: {
  pulse: { like_count: number; repulse_count: number; quote_count: number; view_count: number };
}) {
  const stats = [
    { label: "Repulses", value: pulse.repulse_count },
    { label: "Quotes", value: pulse.quote_count },
    { label: "Likes", value: pulse.like_count },
  ].filter((stat) => stat.value > 0);

  if (stats.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 border-b border-border px-4 py-3 text-sm">
      {stats.map((stat) => (
        <span key={stat.label}>
          <span className="font-bold tabular-nums">{compactNumber(stat.value)}</span>{" "}
          <span className="text-muted-foreground">{stat.label}</span>
        </span>
      ))}
    </div>
  );
}
