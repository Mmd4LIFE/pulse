"use client";

/** The account list shown while an @mention is being typed. */

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { UserAvatar } from "@/components/pulse/user-avatar";
import { VerifiedBadge } from "@/components/pulse/verified-badge";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { UserSummary } from "@/types/api";

interface Props {
  query: string;
  /** Which row the keyboard is on; ignored on touch, where tapping decides. */
  activeIndex: number;
  onHoverIndex: (index: number) => void;
  onPick: (user: UserSummary) => void;
  onResults: (users: UserSummary[]) => void;
}

export function MentionSuggestions({
  query,
  activeIndex,
  onHoverIndex,
  onPick,
  onResults,
}: Props) {
  const suggestions = useQuery({
    queryKey: ["mentions", query],
    queryFn: () => api.suggestMentions(query),
    // A bare "@" is answered with the accounts you follow, so it is worth asking.
    enabled: true,
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });

  const users = React.useMemo(() => suggestions.data ?? [], [suggestions.data]);

  // Keep the parent's keyboard handling in step with what is on screen.
  React.useEffect(() => {
    onResults(users);
  }, [users, onResults]);

  if (users.length === 0) return null;

  return (
    <ul
      role="listbox"
      aria-label="People to mention"
      className="mt-2 max-h-56 overflow-y-auto overscroll-contain rounded-xl border border-border bg-popover"
    >
      {users.map((user, index) => (
        <li key={user.id}>
          <button
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            onMouseEnter={() => onHoverIndex(index)}
            // Pointer-down, not click: the textarea must not lose focus first,
            // which on mobile would dismiss the keyboard mid-selection.
            onPointerDown={(event) => {
              event.preventDefault();
              onPick(user);
            }}
            className={cn(
              "flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors",
              index === activeIndex ? "bg-accent" : "hover:bg-accent/60",
            )}
          >
            <UserAvatar user={user} linked={false} className="h-8 w-8" />
            <span className="min-w-0 flex-1">
              <span className="flex min-w-0 items-center gap-1">
                <bdi className="truncate text-sm font-semibold">{user.display_name}</bdi>
                {user.is_verified ? <VerifiedBadge className="h-3.5 w-3.5" /> : null}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                @{user.username}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
