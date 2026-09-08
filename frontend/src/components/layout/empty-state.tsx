import { cn } from "@/lib/utils";

interface Props {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, hint, icon, action, className }: Props) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-10 py-20 text-center",
        className,
      )}
    >
      {icon ? <div className="text-muted-foreground/60">{icon}</div> : null}
      <div className="space-y-1.5">
        <h2 className="text-base font-bold">{title}</h2>
        {hint ? (
          <p className="text-sm leading-relaxed text-muted-foreground">{hint}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
