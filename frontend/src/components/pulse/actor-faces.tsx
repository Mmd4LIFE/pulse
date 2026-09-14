"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { avatarTone, cn, initials } from "@/lib/utils";
import type { UserSummary } from "@/types/api";

/**
 * The faces on a grouped notification.
 *
 * Overlapped rather than laid out in a row: the row has to carry a count and a
 * sentence as well, and three separate avatars would take the width those need.
 * The overlap also reads as "these people, together", which is what the group
 * means.
 */
export function ActorFaces({
  actors,
  className,
}: {
  actors: UserSummary[];
  className?: string;
}) {
  if (actors.length === 0) return null;

  return (
    <span className={cn("flex shrink-0 -space-x-2", className)}>
      {actors.map((actor) => (
        <Avatar
          key={actor.id}
          // A ring in the card colour, so overlapping faces stay separable.
          className="h-7 w-7 ring-2 ring-card"
        >
          {actor.avatar_url ? (
            <AvatarImage src={actor.avatar_url} alt={actor.display_name} />
          ) : null}
          <AvatarFallback className={cn("text-[0.6rem]", avatarTone(actor.username))}>
            {initials(actor.display_name)}
          </AvatarFallback>
        </Avatar>
      ))}
    </span>
  );
}

/**
 * "Sara", "Sara and Nima", "Sara, Nima and 12 others".
 *
 * Named rather than counted wherever it fits: a name is recognisable and a
 * number is not, and the whole point of the row is to tell you who.
 */
export function actorSentence(actors: UserSummary[], total: number): string {
  const names = actors.map((a) => a.display_name);
  if (total <= 0 || names.length === 0) return "";
  if (total === 1) return names[0] ?? "";
  if (total === 2 && names.length >= 2) return `${names[0]} and ${names[1]}`;

  const shown = names.slice(0, 2);
  const rest = total - shown.length;
  if (rest <= 0) return shown.join(" and ");
  return `${shown.join(", ")} and ${rest} ${rest === 1 ? "other" : "others"}`;
}
