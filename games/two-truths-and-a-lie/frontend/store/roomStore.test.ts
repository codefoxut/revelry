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
    revealData: null,
    gameOver: null,
    status: "idle",
    closeCode: null,
    kicked: false,
    lastError: null,
    socket: null,
  });
});

describe("roomStore — lie_index security invariant", () => {
  it("stores revealData only from the revealed event, not before", () => {
    expect(getState().revealData).toBeNull();
  });

  it("populates revealData when a revealed event arrives", () => {
    const { onEvent } = captureHandlers();
    onEvent({
      type: "revealed",
      lie_index: 1,
      correct_voters: ["p1"],
      scores_delta: { p1: 100 },
    });
    expect(getState().revealData).toEqual({
      lieIndex: 1,
      correctVoters: ["p1"],
      scoresDelta: { p1: 100 },
    });
  });

  it("does NOT expose lie_index via room.game_state before reveal", () => {
    const { onEvent } = captureHandlers();
    onEvent({
      type: "room_state",
      room: buildRoom({ phase: "voting", lie_index: null }),
    });
    expect(getState().room?.game_state?.lie_index).toBeNull();
  });

  it("clears revealData on reconnect", () => {
    setState({ revealData: { lieIndex: 2, correctVoters: [], scoresDelta: {} } });
    getState().connect("ABCDE", "player-1");
    expect(getState().revealData).toBeNull();
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

describe("roomStore — game_over", () => {
  it("stores final scores from game_over event", () => {
    const { onEvent } = captureHandlers();
    onEvent({ type: "game_over", scores: { p1: 200, p2: 100 } });
    expect(getState().gameOver).toEqual({ scores: { p1: 200, p2: 100 } });
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

function buildRoom(gameStateOverride: Record<string, unknown>) {
  return {
    code: "ABCDE",
    game_type: "two_truths_and_a_lie",
    is_private: false,
    phase: gameStateOverride.phase ?? "in_game",
    max_players: 8,
    invite_url: "http://localhost:4100/room/ABCDE",
    players: [
      { id: "p1", display_name: "Alice", avatar: "cat", is_host: true, is_ready: true, is_spectator: false, connected: true },
      { id: "p2", display_name: "Bob", avatar: "dog", is_host: false, is_ready: true, is_spectator: false, connected: true },
      { id: "p3", display_name: "Carol", avatar: "fox", is_host: false, is_ready: true, is_spectator: false, connected: true },
    ],
    game_state: {
      phase: gameStateOverride.phase ?? "voting",
      round_number: 1,
      total_rounds: 3,
      storyteller_id: "p1",
      statements: ["I have a dog", "I lived in Paris", "I can juggle"],
      voted_count: 0,
      lie_index: gameStateOverride.lie_index ?? null,
      correct_voters: null,
      scores: { p1: 0, p2: 0, p3: 0 },
      ...gameStateOverride,
    },
  };
}
