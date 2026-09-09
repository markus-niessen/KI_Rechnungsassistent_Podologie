import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet, ApiError } from "./client";
import { getPatients } from "./patients";

describe("API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns JSON from a successful GET request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([{ id: 1 }]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiGet<Array<{ id: number }>>("/patients")).resolves.toEqual([{ id: 1 }]);
    expect(fetchMock).toHaveBeenCalledWith("/patients", { headers: { Accept: "application/json" } });
  });

  it("serializes supported query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getPatients({ includeInactive: true, search: "Keller" })).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith("/patients?include_inactive=true&search=Keller", {
      headers: { Accept: "application/json" },
    });
  });

  it("throws an ApiError and preserves FastAPI detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Patient not found" }), { status: 404 })),
    );

    await expect(apiGet("/patients/404")).rejects.toMatchObject<ApiError>({
      name: "ApiError",
      status: 404,
      detail: "Patient not found",
      message: "Patient not found",
    });
  });

  it("returns undefined for 204 No Content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(apiGet<void>("/health")).resolves.toBeUndefined();
  });
});
