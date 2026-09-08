import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Room } from "@/types/room";
import type { ServerEvent } from "@/types/ws-events";

interface CapturedHandlers {
  onEvent: (event: ServerEvent) => void;
  onOpen?: () => void;
  onClose?: (event: { code: number }) => void;
  onReconnecting?: (attempt: number) => void;
}

let captured: CapturedHandlers | null = null;

class FakeRoomSocket {
  constructor(_roomCode: string, _playerId: string, handlers: CapturedHandlers) {
    captured = handlers;
  }
  connect = vi.fn();
  close = vi.fn();
  send = vi.fn();
}

vi.mock("@/services/socket", () => ({
  RoomSocket: FakeRoomSocket,
}));

const { useRoomStore } = await import("./roomStore");

function baseRoom(overrides: Partial<Room> = {}): Room {
  return {
    code: "ABCDE",
    game_type: "spyfall",
    is_private: false,
    phase: "lobby",
    max_players: 20,
    players: [
      { id: "p1", display_name: "Alice", avatar: "fox", is_host: true, is_ready: true, is_spectator: false, connected: true },
      { id: "p2", display_name: "Bob", avatar: "owl", is_host: false, is_ready: false, is_spectator: false, connected: true },
    ],
    invite_url: "https://example.test/room/ABCDE",
    game_state: null,
    ...overrides,
  };
}

beforeEach(() => {
  captured = null;
  useRoomStore.getState().connect("ABCDE", "p1");
});

describe("roomStore", () => {
  it("caches the role_assigned payload for a non-spy player", () => {
    captured!.onEvent({ type: "role_assigned", is_spy: false, location: "bank", role: "Teller" });

    expect(useRoomStore.getState().myRole).toEqual({ isSpy: false, location: "bank", role: "Teller" });
  });

  it("caches the role_assigned payload for the spy with null location/role", () => {
    captured!.onEvent({ type: "role_assigned", is_spy: true, location: null, role: null });

    expect(useRoomStore.getState().myRole).toEqual({ isSpy: true, location: null, role: null });
  });

  it("accumulates vote_cast events into the votes tally", () => {
    captured!.onEvent({ type: "vote_cast", player_id: "p1", target_player_id: "p2" });
    captured!.onEvent({ type: "vote_cast", player_id: "p2", target_player_id: "p1" });

    expect(useRoomStore.getState().votes).toEqual({ p1: "p2", p2: "p1" });
  });

  it("resets votes, discussionTimer, and gameOver when a room_state enters discussion", () => {
    captured!.onEvent({ type: "vote_cast", player_id: "p1", target_player_id: "p2" });
    captured!.onEvent({ type: "discussion_timer_started", duration_seconds: 480 });
    expect(useRoomStore.getState().votes).toEqual({ p1: "p2" });
    expect(useRoomStore.getState().discussionTimer).not.toBeNull();

    captured!.onEvent({
      type: "room_state",
      room: baseRoom({ phase: "in_game", game_state: { phase: "discussion", round_number: 1, alive_player_ids: ["p1", "p2"] } }),
    });

    const state = useRoomStore.getState();
    expect(state.votes).toEqual({});
    expect(state.discussionTimer).toBeNull();
    expect(state.gameOver).toBeNull();
    expect(state.room?.game_state?.phase).toBe("discussion");
  });

  it("keeps votes and discussionTimer when room_state reports a non-discussion phase", () => {
    captured!.onEvent({ type: "vote_cast", player_id: "p1", target_player_id: "p2" });
    captured!.onEvent({ type: "discussion_timer_started", duration_seconds: 480 });

    captured!.onEvent({
      type: "room_state",
      room: baseRoom({ phase: "in_game", game_state: { phase: "voting", round_number: 1, alive_player_ids: ["p1", "p2"] } }),
    });

    const state = useRoomStore.getState();
    expect(state.votes).toEqual({ p1: "p2" });
    expect(state.discussionTimer).not.toBeNull();
  });

  it("sets discussionTimer with a deadline derived from duration_seconds", () => {
    const before = Date.now();
    captured!.onEvent({ type: "discussion_timer_started", duration_seconds: 60 });

    const timer = useRoomStore.getState().discussionTimer;
    expect(timer).not.toBeNull();
    expect(timer!.durationSeconds).toBe(60);
    expect(timer!.deadlineAt).toBeGreaterThanOrEqual(before + 60_000);
  });

  it("updates only the targeted player's connected flag", () => {
    captured!.onEvent({ type: "room_state", room: baseRoom() });

    captured!.onEvent({ type: "player_connection_changed", player_id: "p2", connected: false });

    const players = useRoomStore.getState().room!.players;
    expect(players.find((p) => p.id === "p2")!.connected).toBe(false);
    expect(players.find((p) => p.id === "p1")!.connected).toBe(true);
  });

  it("sets the kicked flag on a kicked event", () => {
    expect(useRoomStore.getState().kicked).toBe(false);

    captured!.onEvent({ type: "kicked" });

    expect(useRoomStore.getState().kicked).toBe(true);
  });

  it("stores the last error", () => {
    captured!.onEvent({ type: "error", code: "invalid_game_state", message: "Nope" });

    expect(useRoomStore.getState().lastError).toEqual({ code: "invalid_game_state", message: "Nope" });
  });

  it("stores the full game_over payload including reveals", () => {
    captured!.onEvent({
      type: "game_over",
      winning_side: "non_spies",
      location: "Bank",
      spy_player_ids: ["p2"],
      accused_player_id: "p2",
      reveals: [
        { player_id: "p1", is_spy: false, role: "Teller" },
        { player_id: "p2", is_spy: true, role: null },
      ],
    });

    const gameOver = useRoomStore.getState().gameOver;
    expect(gameOver).not.toBeNull();
    expect(gameOver!.winningSide).toBe("non_spies");
    expect(gameOver!.location).toBe("Bank");
    expect(gameOver!.spyPlayerIds).toEqual(["p2"]);
    expect(gameOver!.accusedPlayerId).toBe("p2");
    expect(gameOver!.reveals).toEqual([
      { player_id: "p1", is_spy: false, role: "Teller" },
      { player_id: "p2", is_spy: true, role: null },
    ]);
  });
});
