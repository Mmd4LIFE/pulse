import { Skeleton } from "@/components/ui/skeleton";

export function PulseSkeleton() {
  return (
    <div className="flex gap-3 border-b border-border px-4 py-3.5">
      <Skeleton className="h-11 w-11 shrink-0 rounded-full" />
      <div className="flex-1 space-y-2.5 py-0.5">
        <Skeleton className="h-3.5 w-40" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
        <div className="flex gap-10 pt-1.5">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-3 w-8" />
        </div>
      </div>
    </div>
  );
}
