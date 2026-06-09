import type { ApiEnvelope, ApiResult } from "./types";

export class NetworkRequestError extends Error {
  offline: boolean;

  constructor(message = "Network request failed") {
    super(message);
    this.name = "NetworkRequestError";
    this.offline = true;
  }
}

async function parseEnvelope<T>(response: Response): Promise<ApiEnvelope<T> | null> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as ApiEnvelope<T>;
  } catch {
    return null;
  }
}

async function request<T>(input: RequestInfo | URL, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const response = await fetch(input, init);
    const body = await parseEnvelope<T>(response);
    return {
      status: response.status,
      ok: response.ok,
      body
    };
  } catch (error) {
    throw new NetworkRequestError(
      error instanceof Error ? error.message : "Network request failed"
    );
  }
}

function mergeInit(base: RequestInit, override?: RequestInit): RequestInit {
  if (!override) {
    return base;
  }

  const mergedHeaders = new Headers(base.headers || {});
  const incomingHeaders = new Headers(override.headers || {});
  incomingHeaders.forEach((value, key) => {
    mergedHeaders.set(key, value);
  });

  return {
    ...base,
    ...override,
    headers: mergedHeaders
  };
}

export function getJson<T>(url: string, init?: RequestInit): Promise<ApiResult<T>> {
  return request<T>(
    url,
    mergeInit(
      {
        headers: {
          Accept: "application/json"
        }
      },
      init
    )
  );
}

export function postJson<T>(url: string, payload: unknown, init?: RequestInit): Promise<ApiResult<T>> {
  return request<T>(
    url,
    mergeInit(
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      },
      init
    )
  );
}

export function patchJson<T>(url: string, payload: unknown, init?: RequestInit): Promise<ApiResult<T>> {
  return request<T>(
    url,
    mergeInit(
      {
        method: "PATCH",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      },
      init
    )
  );
}

export function postForm<T>(
  url: string,
  body: URLSearchParams | FormData,
  init?: RequestInit
): Promise<ApiResult<T>> {
  return request<T>(
    url,
    mergeInit(
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest"
        },
        body
      },
      init
    )
  );
}
