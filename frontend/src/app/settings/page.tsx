"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { AppFrame } from "@/components/layout/app-frame";
import { PageHeader } from "@/components/layout/page-header";
import { UserAvatar } from "@/components/pulse/user-avatar";
import { ChannelCard } from "@/components/settings/channel-card";
import { PrivacyCard } from "@/components/settings/privacy-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import { haptics } from "@/lib/telegram";
import { useAuth } from "@/providers/auth-provider";

const LIMITS = { display_name: 64, bio: 200, location: 64, website: 200 };

export default function SettingsPage() {
  const { user, setUser } = useAuth();

  const [form, setForm] = React.useState({
    username: user?.username ?? "",
    display_name: user?.display_name ?? "",
    bio: user?.bio ?? "",
    location: user?.location ?? "",
    website: user?.website ?? "",
  });

  const save = useMutation({
    mutationFn: () => api.updateProfile(form),
    onSuccess: (updated) => {
      setUser(updated);
      haptics.notify("success");
      toast.success("Profile saved.");
    },
    onError: (error) => {
      haptics.notify("error");
      toast.error(
        error instanceof ApiError ? error.message : "Could not save your profile.",
      );
    },
  });

  if (!user) return null;

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const dirty =
    form.username !== user.username ||
    form.display_name !== user.display_name ||
    form.bio !== (user.bio ?? "") ||
    form.location !== (user.location ?? "") ||
    form.website !== (user.website ?? "");

  return (
    <AppFrame
      hideCompose
      header={
        <PageHeader
          title="Edit profile"
          showBack
          action={
            <Button
              size="sm"
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </Button>
          }
        />
      }
    >
      <div className="space-y-6 px-4 py-5">
        <div className="flex items-center gap-4">
          <UserAvatar user={user} linked={false} className="h-16 w-16" />
          <p className="text-sm text-muted-foreground">
            Your picture comes from Telegram and updates automatically.
          </p>
        </div>

        <Field label="Username" hint="Letters, numbers and underscore. 3–32 characters.">
          <div className="relative">
            <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">
              @
            </span>
            <Input
              value={form.username}
              onChange={(event) => set("username")(event.target.value)}
              maxLength={32}
              className="pl-8"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
          </div>
        </Field>

        <Field label="Name">
          <Input
            value={form.display_name}
            onChange={(event) => set("display_name")(event.target.value)}
            maxLength={LIMITS.display_name}
          />
        </Field>

        <Field label="Bio" counter={`${form.bio.length}/${LIMITS.bio}`}>
          <Textarea
            value={form.bio}
            onChange={(event) => set("bio")(event.target.value)}
            maxLength={LIMITS.bio}
            rows={3}
            placeholder="Tell people who you are"
            className="rounded-xl border border-border bg-secondary/40 px-4 py-3 text-[15px]"
          />
        </Field>

        <Field label="Location">
          <Input
            value={form.location}
            onChange={(event) => set("location")(event.target.value)}
            maxLength={LIMITS.location}
            placeholder="Where you are"
          />
        </Field>

        <Field label="Website">
          <Input
            value={form.website}
            onChange={(event) => set("website")(event.target.value)}
            maxLength={LIMITS.website}
            placeholder="example.com"
            inputMode="url"
            autoCapitalize="none"
          />
        </Field>

        <div className="h-px bg-border" />
        <PrivacyCard />

        <div className="h-px bg-border" />
        <ChannelCard />

        <div className="rounded-xl bg-secondary/50 px-4 py-3 text-xs text-muted-foreground">
          Signed in as Telegram ID {user.telegram_id}. Pulse never sees your phone
          number or messages.
        </div>
      </div>
    </AppFrame>
  );
}

function Field({
  label,
  hint,
  counter,
  children,
}: {
  label: string;
  /** Guidance, shown under the control so it can wrap freely. */
  hint?: string;
  /** A short value pinned to the right of the label, such as "30/200". */
  counter?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-semibold">{label}</span>
        {counter ? (
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
            {counter}
          </span>
        ) : null}
      </span>
      {children}
      {hint ? (
        <span className="block text-xs leading-relaxed text-muted-foreground">{hint}</span>
      ) : null}
    </label>
  );
}
