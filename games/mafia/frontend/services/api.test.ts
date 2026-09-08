import { afterEach, describe, expect, it, vi } from "vitest";
import { getGameInfo } from "./api";
import type { GameInfo } from "@/types/game-info";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getGameInfo", () => {
  const gameInfo: GameInfo = {
    roles: [],
    phases: [],
    tie_breakers: [],
    rules: [],
    faq: [],
  };

  it("fetches the game-info endpoint and returns the parsed payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(gameInfo));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getGameInfo();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/game-info");
    expect(result).toEqual(gameInfo);
  });

  it("throws with the server's error detail on a failed request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "boom" }, false, 500));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getGameInfo()).rejects.toThrow("boom");
  });
});
