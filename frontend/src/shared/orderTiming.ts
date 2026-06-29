export type OrderTimingTone = "on-time" | "warning" | "critical";

export type OrderTimingState = {
  tone: OrderTimingTone;
  delayMinutes: number;
};

export type KitchenTaskTimingInput = {
  status: string;
  item_created_at: string;
  estimated_time: number | null;
  started_at: string | null;
  depends_on_sequence: number | null;
  can_start: boolean;
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

export function getKitchenTaskTimingState(
  task: KitchenTaskTimingInput,
  now: number,
): OrderTimingState {
  const isBlocked = task.status !== "IN_PROGRESS" && !task.can_start;
  if (task.status === "COMPLETED" || isBlocked) {
    return { tone: "on-time", delayMinutes: 0 };
  }

  const timingStartedAt =
    task.depends_on_sequence !== null && task.started_at
      ? task.started_at
      : task.item_created_at;
  return getOrderTimingState(timingStartedAt, task.estimated_time, now);
}

export function getWorstTimingState(states: OrderTimingState[]): OrderTimingState {
  return states.reduce<OrderTimingState>((worst, current) => {
    const rank = { "on-time": 0, warning: 1, critical: 2 } as const;
    if (rank[current.tone] > rank[worst.tone]) return current;
    if (rank[current.tone] === rank[worst.tone] && current.delayMinutes > worst.delayMinutes) {
      return current;
    }
    return worst;
  }, { tone: "on-time", delayMinutes: 0 });
}
