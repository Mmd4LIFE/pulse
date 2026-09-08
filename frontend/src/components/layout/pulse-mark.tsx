import { cn } from "@/lib/utils";

/** The Pulse wordmark glyph: a heartbeat trace inside a rounded square. */
export function PulseMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={cn("h-7 w-7", className)}
    >
      <rect width="32" height="32" rx="9" className="fill-current opacity-15" />
      <path
        d="M5 16.5h4.2l2.4-6.8a1 1 0 0 1 1.9.06l3.6 12.4a1 1 0 0 0 1.92.02l2.3-7.5a1 1 0 0 1 .96-.68H27"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
