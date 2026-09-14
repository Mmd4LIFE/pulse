"use client";

/**
 * The notification inbox.
 *
 * Three ideas carry it. Rows are grouped, because forty people liking one
 * pulse is one thing that happened. Follow requests get their own tab, because
 * a queue of decisions is not a record of events and burying it in the second
 * loses it. And rows are dated into sections, because "today" and "three weeks
 * ago" are read very differently and a column of relative timestamps makes you
 * work that out line by line.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  Bell,
  Check,
  Heart,
  Inbox,
  Lock,
  MessageCircle,
  Quote,
  Repeat2,
  UserCheck,
  UserPlus,
  X,
} from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { toast } from "sonner";

import { AppFrame } from "@/components/layout/app-frame";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { ActorFaces, actorSentence } from "@/components/pulse/actor-faces";
import { PulseSkeleton } from "@/components/pulse/pulse-skeleton";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";
import { detectDirection } from "@/lib/direction";
import { haptics } from "@/lib/telegram";
import { cn, relativeTime } from "@/lib/utils";
import type { NotificationGroup, NotificationTab, NotificationType } from "@/types/api";

const ICONS: Record<NotificationType, React.ComponentType<{ className?: string }>> = {
  like: Heart,
  reply: MessageCircle,
  repulse: Repeat2,
  quote: Quote,
  follow: UserPlus,
  mention: AtSign,
  follow_request: Lock,
  follow_accepted: UserCheck,
};

const TONES: Record<NotificationType, string> = {
  like: "bg-like/10 text-like",
  reply: "bg-primary/10 text-primary",
  repulse: "bg-repulse/10 text-repulse",
  quote: "bg-primary/10 text-primary",
  follow: "bg-primary/10 text-primary",
  mention: "bg-primary/10 text-primary",
  follow_request: "bg-amber-500/10 text-amber-600",
  follow_accepted: "bg-repulse/10 text-repulse",
};

/** Singular and plural, so a row never reads "1 people liked". */
const VERBS: Record<NotificationType, [string, string]> = {
  like: ["liked your pulse", "liked your pulse"],
  reply: ["replied to you", "replied to you"],
  repulse: ["repulsed your pulse", "repulsed your pulse"],
  quote: ["quoted your pulse", "quoted your pulse"],
  follow: ["followed you", "followed you"],
  mention: ["mentioned you", "mentioned you"],
  follow_request: ["asked to follow you", "asked to follow you"],
  follow_accepted: ["accepted your follow request", "accepted your follow request"],
};

const TABS: { value: NotificationTab; label: string }[] = [
  { value: "all", label: "All" },
  { value: "mentions", label: "Mentions" },
  { value: "requests", label: "Requests" },
];

export default function NotificationsPage() {
  const [tab, setTab] = React.useState<NotificationTab>("all");
  const queryClient = useQueryClient();

  const counts = useQuery({
    queryKey: ["notifications", "counts"],
    queryFn: () => api.unreadByTab(),
    refetchInterval: 45_000,
  });

  const feed = useInfiniteFeed(
    ["notifications", tab],
    (page) => api.notifications(tab, page),
  );

  const markRead = useMutation({
    mutationFn: (which: NotificationTab) => api.markAllRead(which),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // Opening a tab is the acknowledgement, but only for that tab: a pending
  // request must not look attended to because Mentions was read.
  const unreadHere = feed.items.some((g) => !g.is_read);
  React.useEffect(() => {
    if (unreadHere && tab !== "requests" && !markRead.isPending) markRead.mutate(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unreadHere, tab]);

  const sections = React.useMemo(() => groupByAge(feed.items), [feed.items]);

  return (
    <AppFrame
      header={
        <PageHeader
          title="Notifications"
          action={
            feed.items.some((g) => !g.is_read) ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => markRead.mutate(tab)}
                disabled={markRead.isPending}
              >
                Mark read
              </Button>
            ) : undefined
          }
        >
          <Tabs value={tab} onValueChange={(v) => setTab(v as NotificationTab)}>
            <TabsList className="px-3">
              {TABS.map((entry) => {
                const badge = counts.data?.[entry.value] ?? 0;
                return (
                  <TabsTrigger key={entry.value} value={entry.value}>
                    <span className="flex items-center gap-1.5">
                      {entry.label}
                      {badge > 0 ? (
                        <span className="rounded-full bg-primary px-1.5 py-px text-2xs font-bold leading-none text-primary-foreground">
                          {badge > 99 ? "99+" : badge}
                        </span>
                      ) : null}
                    </span>
                  </TabsTrigger>
                );
              })}
            </TabsList>
          </Tabs>
        </PageHeader>
      }
    >
      {feed.isLoading ? (
        <div className="pt-3">
          <PulseSkeleton />
          <PulseSkeleton />
          <PulseSkeleton />
        </div>
      ) : feed.items.length === 0 ? (
        <EmptyState
          className="mx-3 mt-3 surface"
          icon={tab === "requests" ? <Inbox className="h-10 w-10" /> : <Bell className="h-10 w-10" />}
          title={EMPTY[tab].title}
          hint={EMPTY[tab].hint}
        />
      ) : (
        <div className="pt-3">
          {sections.map((section) => (
            <section key={section.label}>
              <h2 className="px-5 pb-1.5 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {section.label}
              </h2>
              {section.items.map((group) => (
                <NotificationRow key={group.key} group={group} />
              ))}
            </section>
          ))}

          {feed.hasNextPage ? (
            <div className="flex justify-center py-6">
              <Button
                variant="outline"
                size="sm"
                onClick={() => feed.fetchNextPage()}
                disabled={feed.isFetchingNextPage}
              >
                {feed.isFetchingNextPage ? "Loading…" : "Load more"}
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </AppFrame>
  );
}

const EMPTY: Record<NotificationTab, { title: string; hint: string }> = {
  all: { title: "Nothing yet", hint: "Likes, replies and new followers will show up here." },
  mentions: { title: "No mentions", hint: "Replies and mentions of you land here." },
  requests: { title: "No requests waiting", hint: "People asking to follow you appear here." },
};

/**
 * Today, Yesterday, This week, Earlier.
 *
 * Sections do the work a column of relative timestamps makes the reader do,
 * which is to notice where recent stops.
 */
function groupByAge(items: NotificationGroup[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86_400_000;

  const buckets: { label: string; items: NotificationGroup[] }[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "This week", items: [] },
    { label: "Earlier", items: [] },
  ];

  for (const item of items) {
    const at = new Date(item.created_at).getTime();
    if (at >= startOfToday) buckets[0]!.items.push(item);
    else if (at >= startOfToday - day) buckets[1]!.items.push(item);
    else if (at >= startOfToday - 7 * day) buckets[2]!.items.push(item);
    else buckets[3]!.items.push(item);
  }
  return buckets.filter((b) => b.items.length > 0);
}

function NotificationRow({ group }: { group: NotificationGroup }) {
  const queryClient = useQueryClient();
  const Icon = ICONS[group.type];
  const single = group.actor_count === 1;
  const who = actorSentence(group.actors, group.actor_count);
  const verb = VERBS[group.type][single ? 0 : 1];
  const isRequest = group.type === "follow_request";

  const decide = useMutation({
    mutationFn: ({ username, approve }: { username: string; approve: boolean }) =>
      approve ? api.approveFollowRequest(username) : api.declineFollowRequest(username),
    onSuccess: (_data, { approve }) => {
      haptics.notify("success");
      toast.success(approve ? "Request approved." : "Request declined.");
      void queryClient.invalidateQueries();
    },
    onError: () => toast.error("Could not update that request."),
  });

  // A request is a decision to make here; everything else is a pointer at
  // something to go and look at.
  const href = isRequest
    ? undefined
    : group.pulse
      ? `/pulse/${group.pulse.id}`
      : group.actors[0]
        ? `/u/${group.actors[0].username}`
        : undefined;

  const body = (
    <>
      <span
        className={cn(
          "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
          TONES[group.type],
        )}
      >
        <Icon className="h-[18px] w-[18px]" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-start justify-between gap-3">
          <ActorFaces actors={group.actors} />
          <time
            dateTime={group.created_at}
            className="shrink-0 pt-1 text-xs text-muted-foreground"
          >
            {relativeTime(group.created_at)}
          </time>
        </span>

        <p className="mt-1.5 text-sm">
          <span className="font-bold">{who}</span>{" "}
          <span className="text-muted-foreground">{verb}</span>
        </p>

        {group.pulse && !group.pulse.is_deleted && group.pulse.content ? (
          <p
            dir={detectDirection(group.pulse.content)}
            className="mt-1 line-clamp-2 text-start text-sm text-muted-foreground"
          >
            {group.pulse.content}
          </p>
        ) : null}

        {isRequest ? (
          <span className="mt-2.5 flex flex-wrap gap-2">
            {group.actors.slice(0, 1).map((actor) => (
              <React.Fragment key={actor.id}>
                <Button
                  size="sm"
                  disabled={decide.isPending}
                  onClick={() =>
                    decide.mutate({ username: actor.username, approve: true })
                  }
                >
                  <Check className="h-4 w-4" />
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={decide.isPending}
                  onClick={() =>
                    decide.mutate({ username: actor.username, approve: false })
                  }
                >
                  <X className="h-4 w-4" />
                  Decline
                </Button>
              </React.Fragment>
            ))}
          </span>
        ) : null}
      </span>
    </>
  );

  const shell = cn(
    "surface mx-3 mb-3 flex gap-3 px-4 py-3.5 transition-colors",
    !group.is_read && "border-primary/30 bg-primary/[0.04]",
    href && "hover:bg-accent/30",
  );

  if (!href) return <div className={shell}>{body}</div>;
  return (
    <Link href={href} className={shell}>
      {body}
    </Link>
  );
}
