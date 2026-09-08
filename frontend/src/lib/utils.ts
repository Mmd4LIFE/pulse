import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** "now", "42s", "9m", "3h", "5d", then an absolute date. */
export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.floor((Date.now() - then) / 1000);

  if (seconds < 5) return "now";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;

  const date = new Date(then);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

export function fullTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function joinedDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

/** 1_234 -> "1.2K". Counts above a thousand are approximations anyway. */
export function compactNumber(value: number): string {
  if (!Number.isFinite(value)) return "0";
  if (Math.abs(value) < 1000) return String(value);
  const units = ["K", "M", "B"];
  let n = value;
  let unit = -1;
  while (Math.abs(n) >= 1000 && unit < units.length - 1) {
    n /= 1000;
    unit += 1;
  }
  const rounded = n >= 100 || Number.isInteger(n) ? Math.round(n) : Math.round(n * 10) / 10;
  return `${rounded}${units[unit]}`;
}

/** Deterministic accent for a handle, used for avatar fallbacks. */
export function avatarTone(seed: string): string {
  const tones = [
    "bg-[#2d7ff9]",
    "bg-[#7c5cff]",
    "bg-[#ef4d7a]",
    "bg-[#f0932b]",
    "bg-[#0eb37a]",
    "bg-[#e0407b]",
    "bg-[#00a8c6]",
  ];
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  return tones[Math.abs(hash) % tones.length] ?? tones[0]!;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return `${parts[0]![0]}${parts[1]![0]}`.toUpperCase();
}
