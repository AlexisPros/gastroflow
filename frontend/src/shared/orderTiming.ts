export type OrderTimingTone = "on-time" | "warning" | "critical";

export type OrderTimingState = {
  tone: OrderTimingTone;
  delayMinutes: number;
};

const CRITICAL_DELAY_MS = 3 * 60 * 1000;

export function getOrderTimingState(
  createdAt: string,
  estimatedTime: number | null,
  now: number,
): OrderTimingState {
  if (!estimatedTime || estimatedTime <= 0) {
    return { tone: "on-time", delayMinutes: 0 };
  }

  const deadline = new Date(createdAt).getTime() + estimatedTime * 60 * 1000;
  const delayMs = now - deadline;
  if (!Number.isFinite(deadline) || delayMs <= 0) {
    return { tone: "on-time", delayMinutes: 0 };
  }

  return {
    tone: delayMs >= CRITICAL_DELAY_MS ? "critical" : "warning",
    delayMinutes: Math.max(1, Math.ceil(delayMs / 60_000)),
  };
}
