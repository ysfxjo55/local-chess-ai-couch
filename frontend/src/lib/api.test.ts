import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, clearToken, getToken, setToken } from "./api";

describe("API client", () => {
  beforeEach(() => {
    clearToken();
    vi.restoreAllMocks();
  });

  it("adds the bearer token and returns successful JSON", async () => {
    setToken("test-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ username: "coach", chesscom_username: null, timezone: "UTC" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await expect(api.me()).resolves.toMatchObject({ username: "coach" });
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/me", expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer test-token" }) }));
  });

  it("clears a stale session and emits an authentication event on 401", async () => {
    setToken("expired");
    const handler = vi.fn();
    window.addEventListener("chess-coach:unauthenticated", handler);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401, headers: { "Content-Type": "application/json" } }));
    await expect(api.me()).rejects.toMatchObject({ status: 401, name: "ApiError" });
    expect(getToken()).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener("chess-coach:unauthenticated", handler);
  });
});
