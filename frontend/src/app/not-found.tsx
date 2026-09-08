import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 px-8 text-center">
      <h1 className="text-2xl font-extrabold">This page does not exist</h1>
      <p className="text-sm text-muted-foreground">
        The link may be broken, or the pulse was removed.
      </p>
      <Button asChild>
        <Link href="/">Back to Pulse</Link>
      </Button>
    </div>
  );
}
