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
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { compactNumber } from "@/lib/utils";

export default function ThreadPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
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

function EngagementBar({ pulse }: { pulse: { quote_count: number } }) {
  if (pulse.quote_count === 0) return null;

  return (
    <div className="surface mx-3 mb-3 px-4 py-3 text-sm">
      <span className="font-bold tabular-nums">
        {compactNumber(pulse.quote_count)}
      </span>{" "}
      <span className="text-muted-foreground">
        {pulse.quote_count === 1 ? "Quote" : "Quotes"}
      </span>
    </div>
  );
}
