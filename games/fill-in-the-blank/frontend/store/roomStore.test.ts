import { describe, it, expect, beforeEach, vi } from "vitest";
import { useRoomStore } from "./roomStore";

vi.mock("@/services/socket", () => {
  return {
    RoomSocket: vi.fn().mockImplementation(() => ({
      connect: vi.fn(),
      send: vi.fn(),
      close: vi.fn(),
    })),
  };
});

function getState() {
  return useRoomStore.getState();
}

function setState(partial: Parameters<typeof useRoomStore.setState>[0]) {
  useRoomStore.setState(partial);
}

beforeEach(() => {
  useRoomStore.setState({
    room: null,
    selfPlayerId: null,
    lastRoundDelta: null,
    gameOver: null,
    status: "idle",
    closeCode: null,
    kicked: false,
    lastError: null,
    socket: null,
  });
});

describe("roomStore — anonymity invariant", () => {
  it("starts with no lastRoundDelta", () => {
    expect(getState().lastRoundDelta).toBeNull();
  });

  it("does NOT expose author_id in submissions via room_state during voting", () => {
    const { onEvent } = captureHandlers();
    onEvent({
      type: "room_state",
      room: buildRoom({ phase: "voting" }),
    });
    const subs = getState().room?.game_state?.submissions;
    for (const sub of subs ?? []) {
      expect(Object.keys(sub)).not.toContain("author_id");
    }
  });

  it("exposes author_id in results during results phase", () => {
    const { onEvent } = captureHandlers();
    onEvent({
      type: "room_state",
      room: buildRoom({ phase: "results" }),
    });
    const results = getState().room?.game_state?.results;
    for (const entry of results ?? []) {
      expect(Object.keys(entry)).toContain("author_id");
    }
  });
});

describe("roomStore — round_over", () => {
  it("populates lastRoundDelta from round_over event", () => {
    const { onEvent } = captureHandlers();
    onEvent({ type: "round_over", scores_delta: { p1: 200, p2: 0 } });
    expect(getState().lastRoundDelta).toEqual({ p1: 200, p2: 0 });
  });
});

describe("roomStore — game_over", () => {
  it("stores final scores from game_over event", () => {
    const { onEvent } = captureHandlers();
    onEvent({ type: "game_over", scores: { p1: 400, p2: 200 } });
    expect(getState().gameOver).toEqual({ scores: { p1: 400, p2: 200 } });
  });
});

describe("roomStore — player_connection_changed", () => {
  it("updates connected flag for the matching player", () => {
    const { onEvent } = captureHandlers();
    onEvent({ type: "room_state", room: buildRoom({}) });
    onEvent({ type: "player_connection_changed", player_id: "p1", connected: false });
    const p1 = getState().room?.players.find((p) => p.id === "p1");
    expect(p1?.connected).toBe(false);
  });
});

describe("roomStore — kicked", () => {
  it("sets kicked flag on kicked event", () => {
    const { onEvent } = captureHandlers();
    onEvent({ type: "kicked" });
    expect(getState().kicked).toBe(true);
  });
});

describe("roomStore — connect resets state", () => {
  it("clears lastRoundDelta on reconnect", () => {
    setState({ lastRoundDelta: { p1: 100 } });
    getState().connect("ABCDE", "player-1");
    expect(getState().lastRoundDelta).toBeNull();
  });

  it("clears gameOver on reconnect", () => {
    setState({ gameOver: { scores: { p1: 300 } } });
    getState().connect("ABCDE", "player-1");
    expect(getState().gameOver).toBeNull();
  });
});

// ---- helpers ----

function captureHandlers() {
  let captured: { onEvent: (e: unknown) => void } = { onEvent: () => {} };
  const { RoomSocket } = vi.mocked(await import("@/services/socket"));
  RoomSocket.mockImplementation((_, __, handlers) => {
    captured = handlers as typeof captured;
    return { connect: vi.fn(), send: vi.fn(), close: vi.fn() };
  });
  getState().connect("ABCDE", "player-1");
  return captured;
}

function buildRoom(overrides: Record<string, unknown>) {
  const phase = (overrides.phase as string) ?? "voting";
  const isResults = phase === "results" || phase === "game_over";

  return {
    code: "ABCDE",
    game_type: "fill_in_the_blank",
    is_private: false,
    phase: "in_game",
    max_players: 8,
    invite_url: "http://localhost:3700/room/ABCDE",
    players: [
      { id: "p1", display_name: "Alice", avatar: "cat", is_host: true, is_ready: true, is_spectator: false, connected: true },
      { id: "p2", display_name: "Bob", avatar: "dog", is_host: false, is_ready: true, is_spectator: false, connected: true },
      { id: "p3", display_name: "Carol", avatar: "fox", is_host: false, is_ready: true, is_spectator: false, connected: true },
    ],
    game_state: {
      phase,
      question_number: 1,
      total_questions: 7,
      prompt: "The worst thing to bring to a job interview is ___.",
      submitted_count: 2,
      submissions: isResults
        ? null
        : [
            { submission_id: "sid-1", text: "a live parrot" },
            { submission_id: "sid-2", text: "my personality" },
          ],
      voted_count: 0,
      results: isResults
        ? [
            { submission_id: "sid-1", text: "a live parrot", author_id: "p1", votes: 2 },
            { submission_id: "sid-2", text: "my personality", author_id: "p2", votes: 1 },
          ]
        : null,
      scores: { p1: 0, p2: 0, p3: 0 },
      ...overrides,
    },
  };
}
