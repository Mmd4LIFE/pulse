"use client";

/** A profile: header, stats, and the four timeline tabs. */

import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Link2, Lock, MapPin, Settings } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";

import { AppFrame } from "@/components/layout/app-frame";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { PulseList } from "@/components/pulse/pulse-list";
import { PulseSkeleton } from "@/components/pulse/pulse-skeleton";
import { UserAvatar } from "@/components/pulse/user-avatar";
import { VerifiedBadge } from "@/components/pulse/verified-badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useInfiniteFeed } from "@/hooks/use-feed";
import { useFollow } from "@/hooks/use-pulse-actions";
import { api } from "@/lib/api";
import { openExternal } from "@/lib/telegram";
import { compactNumber, joinedDate } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { UserPublic } from "@/types/api";

export default function ProfilePage() {
  const params = useParams<{ username: string }>();
  const username = decodeURIComponent(params.username ?? "");
  const { user: me } = useAuth();

  const profile = useQuery({
    queryKey: ["user", username],
    queryFn: () => api.getUser(username),
    enabled: Boolean(username),
  });

  if (profile.isLoading) {
    return (
      <AppFrame header={<PageHeader title="Profile" showBack />}>
        <PulseSkeleton />
        <PulseSkeleton />
      </AppFrame>
    );
  }

  if (profile.isError || !profile.data) {
    return (
      <AppFrame header={<PageHeader title="Profile" showBack />}>
        <EmptyState
          title="Account not found"
          hint={`Nobody here goes by @${username}.`}
        />
      </AppFrame>
    );
  }

  const user = profile.data;
  const isMe = me?.id === user.id;

  return (
    <AppFrame
      header={
        <PageHeader
          title={user.display_name}
          subtitle={`${compactNumber(user.pulses_count)} ${user.pulses_count === 1 ? "pulse" : "pulses"}`}
          showBack
          action={
            isMe ? (
              <Button asChild size="icon" variant="ghost" aria-label="Settings">
                <Link href="/settings">
                  <Settings className="h-5 w-5" />
                </Link>
              </Button>
            ) : undefined
          }
        />
      }
    >
      <ProfileHeader user={user} isMe={isMe} />
      {user.can_view_pulses ? (
        <ProfileTabs username={user.username} />
      ) : (
        <ProtectedNotice user={user} />
      )}
    </AppFrame>
  );
}

function ProfileHeader({ user, isMe }: { user: UserPublic; isMe: boolean }) {
  const follow = useFollow();

  return (
    <section>
      <div className="h-28 w-full bg-gradient-to-br from-primary/25 via-primary/10 to-secondary" />

      <div className="px-4 pb-4">
        <div className="flex items-end justify-between">
          <UserAvatar
            user={user}
            linked={false}
            className="-mt-10 h-20 w-20 border-4 border-background"
          />
          {!isMe ? (
            <Button
              variant={user.is_following || user.follow_requested ? "outline" : "default"}
              disabled={follow.isPending}
              onClick={() =>
                follow.mutate({
                  username: user.username,
                  // Tapping again withdraws a pending request as well as
                  // unfollowing, so both map to the same "off" action.
                  on: !(user.is_following || user.follow_requested),
                })
              }
            >
              {user.is_following
                ? "Following"
                : user.follow_requested
                  ? "Requested"
                  : user.is_private
                    ? "Follow request"
                    : "Follow"}
            </Button>
          ) : (
            <Button asChild variant="outline">
              <Link href="/settings">Edit profile</Link>
            </Button>
          )}
        </div>

        <div className="mt-3">
          <h2 className="flex items-center gap-1.5 text-xl font-extrabold">
            <bdi className="break-anywhere">{user.display_name}</bdi>
            {user.is_verified ? <VerifiedBadge className="h-5 w-5" /> : null}
          </h2>
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span>@{user.username}</span>
            {user.is_private ? (
              <span
                title="Protected account"
                className="inline-flex items-center gap-1 rounded-md bg-secondary px-1.5 py-0.5 text-xs font-medium"
              >
                <Lock className="h-3 w-3" />
                Protected
              </span>
            ) : null}
          </p>
          {user.is_followed_by && !isMe ? (
            <span className="mt-1.5 inline-block rounded-md bg-secondary px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
              Follows you
            </span>
          ) : null}
        </div>

        {user.bio ? (
          <p dir="auto" className="mt-3 whitespace-pre-wrap break-anywhere text-start text-base">
            {user.bio}
          </p>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {user.location ? (
            <span className="flex items-center gap-1">
              <MapPin className="h-4 w-4" />
              {user.location}
            </span>
          ) : null}
          {user.website ? (
            <button
              type="button"
              onClick={() => openExternal(normaliseUrl(user.website!))}
              className="flex items-center gap-1 text-primary hover:underline"
            >
              <Link2 className="h-4 w-4" />
              {user.website.replace(/^https?:\/\//, "")}
            </button>
          ) : null}
          <span className="flex items-center gap-1">
            <CalendarDays className="h-4 w-4" />
            Joined {joinedDate(user.created_at)}
          </span>
        </div>

        <div className="mt-3 flex gap-5 text-sm">
          <Link href={`/u/${user.username}/following`} className="hover:underline">
            <span className="font-bold tabular-nums">
              {compactNumber(user.following_count)}
            </span>{" "}
            <span className="text-muted-foreground">Following</span>
          </Link>
          <Link href={`/u/${user.username}/followers`} className="hover:underline">
            <span className="font-bold tabular-nums">
              {compactNumber(user.followers_count)}
            </span>{" "}
            <span className="text-muted-foreground">Followers</span>
          </Link>
        </div>
      </div>
    </section>
  );
}

function ProtectedNotice({ user }: { user: UserPublic }) {
  return (
    <EmptyState
      className="border-t border-border"
      icon={<Lock className="h-10 w-10" />}
      title="These pulses are protected"
      hint={
        user.follow_requested
          ? `@${user.username} has your follow request. You will see their pulses once they approve it.`
          : `Only people @${user.username} approves can see their pulses.`
      }
    />
  );
}


function ProfileTabs({ username }: { username: string }) {
  const [tab, setTab] = React.useState("pulses");

  const pulses = useInfiniteFeed(
    ["user", username, "pulses"],
    (p) => api.userPulses(username, p),
    { enabled: tab === "pulses" },
  );
  const replies = useInfiniteFeed(
    ["user", username, "replies"],
    (p) => api.userReplies(username, p),
    { enabled: tab === "replies" },
  );
  const media = useInfiniteFeed(
    ["user", username, "media"],
    (p) => api.userMedia(username, p),
    { enabled: tab === "media" },
  );
  const likes = useInfiniteFeed(
    ["user", username, "likes"],
    (p) => api.userLikes(username, p),
    { enabled: tab === "likes" },
  );

  const panes = [
    { value: "pulses", label: "Pulses", feed: pulses, empty: "No pulses yet" },
    { value: "replies", label: "Replies", feed: replies, empty: "No replies yet" },
    { value: "media", label: "Media", feed: media, empty: "No images yet" },
    { value: "likes", label: "Likes", feed: likes, empty: "No likes yet" },
  ];

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList className="sticky top-[57px] z-20">
        {panes.map((pane) => (
          <TabsTrigger key={pane.value} value={pane.value}>
            {pane.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {panes.map((pane) => (
        <TabsContent key={pane.value} value={pane.value}>
          <PulseList
            items={pane.feed.items}
            isLoading={pane.feed.isLoading}
            isError={pane.feed.isError}
            hasNextPage={pane.feed.hasNextPage}
            isFetchingNextPage={pane.feed.isFetchingNextPage}
            fetchNextPage={pane.feed.fetchNextPage}
            refetch={pane.feed.refetch}
            emptyTitle={pane.empty}
          />
        </TabsContent>
      ))}
    </Tabs>
  );
}

function normaliseUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}
