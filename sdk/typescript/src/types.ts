export type GuardAction = "pass" | "flag" | "block";

export type GuardContext = "session" | "none";

export interface GuardResult {
  action: GuardAction;
  session_id: string;
  decided_by: string;
  direction: "input" | "output";
  score?: number | null;
  reason?: string | null;
  modules_triggered: string[];
  context: GuardContext;
  latency_ms: number;
}

export interface Session {
  session_id: string;
  turns: number;
  risk_score: number;
  peak_score: number;
  history: Array<Record<string, unknown>>;
}

export interface HealthResponse {
  status: "ok";
  providers: Record<string, Record<string, unknown>>;
}

export interface GuardInputRequest {
  text: string;
  session_id?: string | null;
  metadata?: Record<string, unknown>;
  dry_run?: boolean;
}

export interface GuardOutputRequest {
  text: string;
  session_id?: string | null;
  metadata?: Record<string, unknown>;
  dry_run?: boolean;
}

export interface BlockedErrorPayload {
  error: "request_blocked";
  message: string;
  reason: string | null | undefined;
  modules_triggered: string[];
}

export function isBlocked(result: GuardResult): boolean {
  return result.action === "block";
}

export function toBlockedErrorPayload(
  result: GuardResult,
  message?: string,
): BlockedErrorPayload {
  return {
    error: "request_blocked",
    message: message ?? "This request was blocked by the content guardrail.",
    reason: result.reason,
    modules_triggered: result.modules_triggered,
  };
}
