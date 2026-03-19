import type { GuardResult } from "./types";

export class DefendError extends Error {
  details?: unknown;

  constructor(message: string, details?: unknown) {
    super(message);
    this.name = "DefendError";
    this.details = details;
  }
}

export class DefendConnectionError extends DefendError {
  constructor(message: string, details?: unknown) {
    super(message, details);
    this.name = "DefendConnectionError";
  }
}

export class DefendBlockedError extends DefendError {
  result: GuardResult;

  constructor(message: string, result: GuardResult) {
    super(message, result);
    this.name = "DefendBlockedError";
    this.result = result;
  }
}

export class DefendHTTPError extends DefendError {
  statusCode: number;
  payload: unknown | undefined;
  headers: Record<string, string> | undefined;

  constructor(
    message: string,
    statusCode: number,
    payload?: unknown,
    headers?: Record<string, string>,
  ) {
    super(message, payload);
    this.name = "DefendHTTPError";
    this.statusCode = statusCode;
    this.payload = payload;
    this.headers = headers;
  }
}
