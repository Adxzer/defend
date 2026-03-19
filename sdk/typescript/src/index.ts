export { DefendClient } from "./client";

export {
  DefendError,
  DefendConnectionError,
  DefendHTTPError,
  DefendBlockedError,
} from "./errors";

export type {
  GuardAction,
  GuardContext,
  GuardResult,
  Session,
  HealthResponse,
  GuardInputRequest,
  GuardOutputRequest,
  BlockedErrorPayload,
} from "./types";

export { isBlocked, toBlockedErrorPayload } from "./types";
