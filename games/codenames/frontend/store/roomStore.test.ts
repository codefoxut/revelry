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
    game_type: "codenames",
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
  it("caches the team_assigned payload", () => {
    captured!.onEvent({ type: "team_assigned", team: "red", role: "spymaster" });

    expect(useRoomStore.getState().myAssignment).toEqual({ team: "red", role: "spymaster" });
  });

  it("caches the spymaster_view color list", () => {
    const colors = Array(25).fill("neutral");
    captured!.onEvent({ type: "spymaster_view", colors });

    expect(useRoomStore.getState().spymasterColors).toEqual(colors);
  });

  it("does not populate spymasterColors for a guesser", () => {
    captured!.onEvent({ type: "team_assigned", team: "blue", role: "guesser" });

    expect(useRoomStore.getState().spymasterColors).toBeNull();
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

  it("stores the full game_over payload", () => {
    captured!.onEvent({
      type: "game_over",
      winning_side: "red",
      reason: "all_words_found",
      colors: Array(25).fill("red"),
    });

    const gameOver = useRoomStore.getState().gameOver;
    expect(gameOver).not.toBeNull();
    expect(gameOver!.winningSide).toBe("red");
    expect(gameOver!.reason).toBe("all_words_found");
    expect(gameOver!.colors).toHaveLength(25);
  });

  it("replaces the room snapshot on room_state without touching cached assignment state", () => {
    captured!.onEvent({ type: "team_assigned", team: "red", role: "guesser" });
    captured!.onEvent({
      type: "room_state",
      room: baseRoom({
        phase: "in_game",
        game_state: {
          phase: "red_turn",
          round_number: 1,
          current_team: "red",
          current_clue: null,
          board: [],
          red_remaining: 9,
          blue_remaining: 8,
        },
      }),
    });

    const state = useRoomStore.getState();
    expect(state.room?.game_state?.phase).toBe("red_turn");
    expect(state.myAssignment).toEqual({ team: "red", role: "guesser" });
  });
});
