"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AtSign, Bell, Heart, MessageCircle, Quote, Repeat2, UserPlus } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { AppFrame } from "@/components/layout/app-frame";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { PulseSkeleton } from "@/components/pulse/pulse-skeleton";
import { UserAvatar } from "@/components/pulse/user-avatar";
import { Button } from "@/components/ui/button";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { api } from "@/lib/api";
import { cn, relativeTime } from "@/lib/utils";
import type { AppNotification, NotificationType } from "@/types/api";

const ICONS: Record<NotificationType, React.ComponentType<{ className?: string }>> = {
  like: Heart,
  reply: MessageCircle,
  repulse: Repeat2,
  quote: Quote,
  follow: UserPlus,
  mention: AtSign,
};

const TONES: Record<NotificationType, string> = {
  like: "text-like",
  reply: "text-primary",
  repulse: "text-repulse",
  quote: "text-primary",
  follow: "text-primary",
  mention: "text-primary",
};

const VERBS: Record<NotificationType, string> = {
  like: "liked your pulse",
  reply: "replied to your pulse",
  repulse: "repulsed your pulse",
  quote: "quoted your pulse",
  follow: "started following you",
  mention: "mentioned you",
};

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const feed = useInfiniteFeed(["notifications"], (params) => api.notifications(params));

  const markRead = useMutation({
    mutationFn: () => api.markAllRead(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const hasUnread = feed.items.some((n) => !n.is_read);

  // Opening the screen is the acknowledgement; clear the badge on arrival.
  React.useEffect(() => {
    if (hasUnread && !markRead.isPending) markRead.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasUnread]);

  return (
    <AppFrame
      header={
        <PageHeader
          title="Notifications"
          action={
            hasUnread ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => markRead.mutate()}
                disabled={markRead.isPending}
              >
                Mark read
              </Button>
            ) : undefined
          }
        />
      }
    >
      {feed.isLoading ? (
        <div>
          <PulseSkeleton />
          <PulseSkeleton />
          <PulseSkeleton />
        </div>
      ) : feed.items.length === 0 ? (
        <EmptyState
          icon={<Bell className="h-10 w-10" />}
          title="Nothing yet"
          hint="Likes, replies and new followers will show up here."
        />
      ) : (
        <ul>
          {feed.items.map((item) => (
            <li key={item.id}>
              <NotificationRow notification={item} />
            </li>
          ))}
        </ul>
      )}

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
    </AppFrame>
  );
}

function NotificationRow({ notification }: { notification: AppNotification }) {
  const Icon = ICONS[notification.type];
  const href = notification.pulse
    ? `/pulse/${notification.pulse.id}`
    : `/u/${notification.actor.username}`;

  return (
    <Link
      href={href}
      className={cn(
        "flex gap-3 border-b border-border px-4 py-3.5 transition-colors hover:bg-accent/40",
        !notification.is_read && "bg-primary/[0.06]",
      )}
    >
      <span className={cn("mt-1 shrink-0", TONES[notification.type])}>
        <Icon className="h-5 w-5" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <UserAvatar user={notification.actor} className="h-7 w-7" linked={false} />
          <p className="min-w-0 flex-1 text-sm">
            <span className="font-bold">{notification.actor.display_name}</span>{" "}
            <span className="text-muted-foreground">{VERBS[notification.type]}</span>
          </p>
          <time
            dateTime={notification.created_at}
            className="shrink-0 text-xs text-muted-foreground"
          >
            {relativeTime(notification.created_at)}
          </time>
        </div>

        {notification.pulse && !notification.pulse.is_deleted ? (
          <p className="mt-1.5 line-clamp-2 pl-9 text-sm text-muted-foreground">
            {notification.pulse.content}
          </p>
        ) : null}
      </div>
    </Link>
  );
}
