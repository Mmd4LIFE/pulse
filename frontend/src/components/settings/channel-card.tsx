"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, Megaphone, Send, Unplug } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import { confirmAction, haptics } from "@/lib/telegram";
import { useAuth } from "@/providers/auth-provider";

// The @handle is only correct when the build was given one; otherwise name the
// bot in prose rather than printing a bare "@".
const BOT_USERNAME = process.env.NEXT_PUBLIC_BOT_USERNAME;
const BOT_NAME = BOT_USERNAME ? `@${BOT_USERNAME}` : "the Pulse bot";

export function ChannelCard() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [reference, setReference] = React.useState("");

  const channel = useQuery({
    queryKey: ["channel"],
    queryFn: () => api.myChannel(),
    enabled: Boolean(user),
  });

  const connect = useMutation({
    mutationFn: () => api.connectChannel(reference.trim()),
    onSuccess: (connected) => {
      haptics.notify("success");
      toast.success(`Connected ${connected.username ? `@${connected.username}` : connected.title}.`);
      setReference("");
      void queryClient.invalidateQueries({ queryKey: ["channel"] });
    },
    onError: (error) => {
      haptics.notify("error");
      toast.error(
        error instanceof ApiError ? error.message : "Could not connect that channel.",
      );
    },
  });

  const disconnect = useMutation({
    mutationFn: () => api.disconnectChannel(),
    onSuccess: () => {
      toast.success("Channel disconnected.");
      void queryClient.invalidateQueries({ queryKey: ["channel"] });
    },
    onError: () => toast.error("Could not disconnect."),
  });

  const test = useMutation({
    mutationFn: () => api.testChannel(),
    onSuccess: (result) => {
      toast.success(result.message);
      void queryClient.invalidateQueries({ queryKey: ["channel"] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Test message failed."),
  });

  const connected = channel.data;

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Channel</h2>

      {connected ? (
        <div className="space-y-3 rounded-xl border border-border p-4">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Megaphone className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{connected.title}</p>
              {connected.username ? (
                <p className="truncate text-xs text-muted-foreground">
                  @{connected.username}
                </p>
              ) : null}
            </div>
          </div>

          {connected.can_post ? (
            <p className="flex items-start gap-2 text-xs text-muted-foreground">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-repulse" />
              Ready. When you write a pulse you can tick &ldquo;also post to this
              channel&rdquo;.
            </p>
          ) : (
            <p className="flex items-start gap-2 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              {connected.last_error ??
                "Telegram refused the last message. Check the bot is still an admin."}
            </p>
          )}

          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={test.isPending}
              onClick={() => test.mutate()}
            >
              {test.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Send a test
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive"
              disabled={disconnect.isPending}
              onClick={async () => {
                if (await confirmAction("Disconnect this channel?")) disconnect.mutate();
              }}
            >
              <Unplug className="h-4 w-4" />
              Disconnect
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3 rounded-xl border border-border p-4">
          <p className="text-xs leading-relaxed text-muted-foreground">
            Mirror your pulses to a channel you run. First add{" "}
            <span className="font-semibold text-foreground">{BOT_NAME}</span> to the
            channel as an administrator with{" "}
            <span className="font-semibold text-foreground">Post Messages</span>{" "}
            enabled, then enter the channel below.
          </p>

          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (reference.trim()) connect.mutate();
            }}
          >
            <Input
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              placeholder="@yourchannel"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
            <Button type="submit" disabled={!reference.trim() || connect.isPending}>
              {connect.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Connect
            </Button>
          </form>
        </div>
      )}
    </section>
  );
}
