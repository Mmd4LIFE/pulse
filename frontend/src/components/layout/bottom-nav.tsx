"use client";

import { Bell, Bookmark, Home, Search, User } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { haptics } from "@/lib/telegram";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";

export function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api.unreadCount(),
    refetchInterval: 45_000,
    enabled: Boolean(user),
  });

  const items = [
    { href: "/", label: "Home", icon: Home },
    { href: "/explore", label: "Explore", icon: Search },
    { href: "/notifications", label: "Alerts", icon: Bell, badge: unread?.count ?? 0 },
    { href: "/bookmarks", label: "Saved", icon: Bookmark },
    { href: user ? `/u/${user.username}` : "/", label: "You", icon: User },
  ];

  return (
    <nav className="sticky bottom-0 z-30 mt-auto border-t border-border bg-background/90 backdrop-blur-xl safe-bottom">
      <ul className="mx-auto flex max-w-[600px] items-stretch">
        {items.map(({ href, label, icon: Icon, badge }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href) && href !== "/";

          return (
            <li key={label} className="flex-1">
              <Link
                href={href}
                onClick={() => haptics.select()}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "tap-target relative flex h-[54px] flex-col items-center justify-center gap-0.5",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                <span className="relative">
                  <Icon
                    className={cn("h-[22px] w-[22px]", active && "stroke-[2.5]")}
                  />
                  {badge && badge > 0 ? (
                    <span className="absolute -right-2 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-none text-destructive-foreground">
                      {badge > 99 ? "99+" : badge}
                    </span>
                  ) : null}
                </span>
                <span className="text-[10px] font-semibold tracking-tight">{label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
