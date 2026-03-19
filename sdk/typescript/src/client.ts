import {
  DefendBlockedError,
  DefendConnectionError,
  DefendHTTPError,
} from "./errors";
import type {
  GuardResult,
  HealthResponse,
  Session,
} from "./types";
import { isBlocked } from "./types";

type FetchLike = typeof fetch;

export interface DefendClientOptions {
  apiKey: string;
  baseUrl?: string;
  provider?: string;
  modules?: string[];
  confidenceThreshold?: number;
  timeoutMs?: number;
  raiseOnBlock?: boolean;
  fetch?: FetchLike;
}

export interface GuardCallOptions {
  sessionId?: string;
  dryRun?: boolean;
  metadata?: Record<string, unknown>;
}

function normalizeBaseUrl(baseUrl: string): string {
  const url = baseUrl.replace(/\/+$/, "");
  if (url.endsWith("/v1")) {
    return url;
  }
  return `${url}/v1`;
}

function normalizeHeaders(headers: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  headers.forEach((value, key) => {
    out[key] = value;
  });
  return out;
}

export class DefendClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly raiseOnBlock: boolean;
  private readonly fetchImpl: FetchLike;
  private readonly defaultMetadata: Record<string, unknown>;
  private lastSessionId: string | null;

  constructor(options: DefendClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = normalizeBaseUrl(options.baseUrl ?? "http://localhost:8000");
    this.timeoutMs = options.timeoutMs ?? 10000;
    this.raiseOnBlock = options.raiseOnBlock ?? false;
    this.fetchImpl = options.fetch ?? fetch;
    this.lastSessionId = null;

    this.defaultMetadata = {};
    if (options.provider != null) {
      this.defaultMetadata.provider = options.provider;
    }
    if (options.modules != null) {
      this.defaultMetadata.modules = options.modules;
    }
    if (options.confidenceThreshold != null) {
      this.defaultMetadata.confidence_threshold = options.confidenceThreshold;
    }
  }

  private async requestJson(
    method: string,
    path: string,
    jsonBody?: Record<string, unknown>,
  ): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    let response: Response;
    try {
      const init: RequestInit = {
        method,
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        signal: controller.signal,
      };
      if (jsonBody != null) {
        init.body = JSON.stringify(jsonBody);
      }

      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        ...init,
      });
    } catch (error) {
      clearTimeout(timer);
      throw new DefendConnectionError(
        `Failed to connect to Defend at ${this.baseUrl}`,
        error,
      );
    }
    clearTimeout(timer);

    const text = await response.text();
    let payload: unknown = text;
    if (text.length > 0) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    } else {
      payload = null;
    }

    if (!response.ok) {
      throw new DefendHTTPError(
        `Defend API error calling ${method} ${path}`,
        response.status,
        payload,
        normalizeHeaders(response.headers),
      );
    }

    return payload;
  }

  async health(): Promise<HealthResponse> {
    return (await this.requestJson("GET", "/health")) as HealthResponse;
  }

  async input(text: string, options: GuardCallOptions = {}): Promise<GuardResult> {
    const mergedMeta = {
      ...this.defaultMetadata,
      ...(options.metadata ?? {}),
    };

    const body: Record<string, unknown> = {
      text,
      session_id: options.sessionId ?? null,
      metadata: mergedMeta,
    };
    if (options.dryRun) {
      body.dry_run = true;
    }

    const result = (await this.requestJson("POST", "/guard/input", body)) as GuardResult;
    this.lastSessionId = result.session_id;
    if (this.raiseOnBlock && isBlocked(result)) {
      throw new DefendBlockedError("Input blocked", result);
    }
    return result;
  }

  async output(text: string, options: GuardCallOptions = {}): Promise<GuardResult> {
    const mergedMeta = {
      ...this.defaultMetadata,
      ...(options.metadata ?? {}),
    };
    const sid = options.sessionId ?? this.lastSessionId ?? null;
    const body: Record<string, unknown> = {
      text,
      session_id: sid,
      metadata: mergedMeta,
    };
    if (options.dryRun) {
      body.dry_run = true;
    }

    const result = (await this.requestJson("POST", "/guard/output", body)) as GuardResult;
    if (this.raiseOnBlock && isBlocked(result)) {
      throw new DefendBlockedError("Output blocked", result);
    }
    return result;
  }

  async getSession(sessionId: string): Promise<Session> {
    return (await this.requestJson("GET", `/sessions/${sessionId}`)) as Session;
  }

  async deleteSession(sessionId: string): Promise<void> {
    await this.requestJson("DELETE", `/sessions/${sessionId}`);
  }
}
