"use client";

import Link from "next/link";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { avatarTone, cn, initials } from "@/lib/utils";
import type { UserSummary } from "@/types/api";

interface Props {
  user: Pick<UserSummary, "username" | "display_name" | "avatar_url">;
  className?: string;
  linked?: boolean;
}

export function UserAvatar({ user, className, linked = true }: Props) {
  const avatar = (
    <Avatar className={cn("h-11 w-11", className)}>
      {user.avatar_url ? (
        <AvatarImage src={user.avatar_url} alt={user.display_name} />
      ) : null}
      <AvatarFallback className={avatarTone(user.username)}>
        {initials(user.display_name)}
      </AvatarFallback>
    </Avatar>
  );

  if (!linked) return avatar;

  return (
    <Link
      href={`/u/${user.username}`}
      onClick={(event) => event.stopPropagation()}
      className="shrink-0 rounded-full transition-opacity hover:opacity-85"
      aria-label={`${user.display_name}'s profile`}
    >
      {avatar}
    </Link>
  );
}
