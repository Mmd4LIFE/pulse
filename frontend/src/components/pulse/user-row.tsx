"use client";

import Link from "next/link";

import { UserAvatar } from "@/components/pulse/user-avatar";
import { VerifiedBadge } from "@/components/pulse/verified-badge";
import { Button } from "@/components/ui/button";
import { useFollow } from "@/hooks/use-pulse-actions";
import { useAuth } from "@/providers/auth-provider";
import type { UserPublic } from "@/types/api";

export function UserRow({ user }: { user: UserPublic }) {
  const { user: me } = useAuth();
  const follow = useFollow();
  const isMe = me?.id === user.id;

  return (
    <div className="flex items-start gap-3 border-b border-border px-4 py-3.5">
      <UserAvatar user={user} />
      <div className="min-w-0 flex-1">
        <Link href={`/u/${user.username}`} className="block min-w-0">
          <span className="flex min-w-0 items-center gap-1 font-bold hover:underline">
            <span className="truncate">{user.display_name}</span>
            {user.is_verified ? <VerifiedBadge /> : null}
          </span>
          <span className="block truncate text-sm text-muted-foreground">
            @{user.username}
          </span>
        </Link>
        {user.bio ? (
          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{user.bio}</p>
        ) : null}
      </div>

      {!isMe ? (
        <Button
          size="sm"
          variant={user.is_following ? "outline" : "default"}
          disabled={follow.isPending}
          onClick={() =>
            follow.mutate({ username: user.username, on: !user.is_following })
          }
        >
          {user.is_following ? "Following" : "Follow"}
        </Button>
      ) : null}
    </div>
  );
}
