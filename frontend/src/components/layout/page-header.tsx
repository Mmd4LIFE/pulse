"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { cn } from "@/lib/utils";

interface Props {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  showBack?: boolean;
  action?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  showBack = false,
  action,
  children,
  className,
}: Props) {
  const router = useRouter();

  return (
    <header className={cn("sticky-header", className)}>
      <div className="flex items-center gap-2 px-4 py-3">
        {showBack ? (
          <button
            type="button"
            aria-label="Go back"
            onClick={() => router.back()}
            className="-ml-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-accent"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
        ) : null}

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-extrabold leading-tight">{title}</h1>
          {subtitle ? (
            <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>

        {action}
      </div>
      {children}
    </header>
  );
}
