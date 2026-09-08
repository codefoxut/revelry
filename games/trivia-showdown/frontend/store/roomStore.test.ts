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
    game_type: "trivia_showdown",
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

  it("caches the last judged answer as a transient flash", () => {
    captured!.onEvent({ type: "answer_judged", player_id: "p2", correct: true, score_delta: 100 });

    expect(useRoomStore.getState().lastJudged).toEqual({ playerId: "p2", correct: true, scoreDelta: 100 });
  });

  it("stores the full game_over payload including winner_id", () => {
    captured!.onEvent({
      type: "game_over",
      scores: { p1: 300, p2: 500 },
      winner_id: "p2",
    });

    const gameOver = useRoomStore.getState().gameOver;
    expect(gameOver).toEqual({ scores: { p1: 300, p2: 500 }, winnerId: "p2" });
  });

  it("replaces the room snapshot on room_state without touching cached game-over state", () => {
    captured!.onEvent({
      type: "game_over",
      scores: { p1: 100 },
      winner_id: "p1",
    });
    captured!.onEvent({
      type: "room_state",
      room: baseRoom({
        phase: "in_game",
        game_state: {
          phase: "question_open",
          round_number: 2,
          total_questions: 10,
          category: "Science",
          question: "What planet is closest to the sun?",
          answer: null,
          buzzed_player_id: null,
          locked_out: [],
          scores: { p1: 100, p2: 0 },
        },
      }),
    });

    const state = useRoomStore.getState();
    expect(state.room?.game_state?.phase).toBe("question_open");
    expect(state.gameOver).toEqual({ scores: { p1: 100 }, winnerId: "p1" });
  });
});
