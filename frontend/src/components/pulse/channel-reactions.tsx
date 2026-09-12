import { compactNumber } from "@/lib/utils";

/**
 * The reaction tallies a post carried over from its Telegram channel.
 *
 * Shown rather than folded into Pulse's own like count: these came from a
 * different audience in a different place, and merging them would misreport
 * both.
 */
export function ChannelReactions({
  reactions,
}: {
  reactions: { emoji: string; count: number }[];
}) {
  if (reactions.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-wrap gap-1.5">
      {reactions.map((reaction) => (
        <li
          key={reaction.emoji}
          className="flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs"
          title={`${reaction.count} on Telegram`}
        >
          <span aria-hidden>{reaction.emoji}</span>
          <span className="tabular-nums text-muted-foreground">
            {compactNumber(reaction.count)}
          </span>
        </li>
      ))}
    </ul>
  );
}
