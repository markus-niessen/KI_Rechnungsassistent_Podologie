export type QueryParameters = Record<string, boolean | number | string | null | undefined>;

export class ApiError extends Error {
  readonly detail: unknown;
  readonly status: number;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function buildUrl(path: string, query?: QueryParameters): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null) {
      searchParams.set(key, String(value));
    }
  }

  const queryString = searchParams.toString();
  return queryString ? `${path}?${queryString}` : path;
}

export async function apiGet<T>(path: string, query?: QueryParameters): Promise<T | undefined> {
  const response = await fetch(buildUrl(path, query), {
    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 204) {
    return undefined;
  }

  const payload = await response.json().catch(() => undefined);

  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload ? payload.detail : undefined;
    const message = typeof detail === "string" ? detail : `HTTP ${response.status}`;
    throw new ApiError(response.status, detail, message);
  }

  return payload as T;
}
