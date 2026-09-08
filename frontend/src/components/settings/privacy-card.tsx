"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Lock, LockOpen, X } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { UserAvatar } from "@/components/pulse/user-avatar";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { confirmAction, haptics } from "@/lib/telegram";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";

export function PrivacyCard() {
  const { user, setUser } = useAuth();
  const queryClient = useQueryClient();

  const requests = useQuery({
    queryKey: ["follow-requests"],
    queryFn: () => api.followRequests({ limit: 20 }),
    enabled: Boolean(user?.is_private),
  });

  const toggle = useMutation({
    mutationFn: (isPrivate: boolean) => api.setPrivacy(isPrivate),
    onSuccess: (updated) => {
      setUser(updated);
      haptics.notify("success");
      toast.success(
        updated.is_private ? "Your account is protected." : "Your account is public.",
      );
      void queryClient.invalidateQueries();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not change that."),
  });

  const decide = useMutation({
    mutationFn: ({ username, approve }: { username: string; approve: boolean }) =>
      approve ? api.approveFollowRequest(username) : api.declineFollowRequest(username),
    onSuccess: () => {
      haptics.tap("medium");
      void queryClient.invalidateQueries();
    },
    onError: () => toast.error("Could not update that request."),
  });

  if (!user) return null;

  const onToggle = async () => {
    const goingPrivate = !user.is_private;
    if (!goingPrivate) {
      const ok = await confirmAction(
        "Make your account public? Anyone will be able to see your pulses, and everyone waiting to follow you will be approved.",
      );
      if (!ok) return;
    }
    toggle.mutate(goingPrivate);
  };

  const pending = requests.data?.items ?? [];

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Privacy</h2>

      <button
        type="button"
        onClick={onToggle}
        disabled={toggle.isPending}
        className="flex w-full items-center gap-3 rounded-xl border border-border p-4 text-left transition-colors hover:bg-accent/40 disabled:opacity-60"
      >
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
            user.is_private
              ? "bg-primary/15 text-primary"
              : "bg-secondary text-muted-foreground",
          )}
        >
          {user.is_private ? <Lock className="h-5 w-5" /> : <LockOpen className="h-5 w-5" />}
        </span>

        <span className="min-w-0 flex-1">
          <span className="block font-semibold">Protect my pulses</span>
          <span className="block text-xs leading-relaxed text-muted-foreground">
            {user.is_private
              ? "Only approved followers can see your pulses. New followers have to ask."
              : "Anyone can see your pulses and follow you without asking."}
          </span>
        </span>

        {/* A switch, drawn here rather than pulled in as another dependency. */}
        <span
          aria-hidden
          className={cn(
            "relative h-6 w-11 shrink-0 rounded-full transition-colors",
            user.is_private ? "bg-primary" : "bg-border",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all",
              user.is_private ? "left-[22px]" : "left-0.5",
            )}
          />
        </span>
      </button>

      {user.is_private ? (
        <div className="rounded-xl border border-border">
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-sm font-semibold">Follow requests</span>
            <span className="text-xs text-muted-foreground">
              {pending.length === 0 ? "None waiting" : `${pending.length} waiting`}
            </span>
          </div>

          {pending.map((person) => (
            <div
              key={person.id}
              className="flex items-center gap-3 border-t border-border px-4 py-3"
            >
              <UserAvatar user={person} className="h-9 w-9" />
              <Link href={`/u/${person.username}`} className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">
                  {person.display_name}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  @{person.username}
                </span>
              </Link>
              <Button
                size="icon"
                aria-label={`Approve @${person.username}`}
                disabled={decide.isPending}
                onClick={() => decide.mutate({ username: person.username, approve: true })}
              >
                <Check className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant="outline"
                aria-label={`Decline @${person.username}`}
                disabled={decide.isPending}
                onClick={() => decide.mutate({ username: person.username, approve: false })}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
