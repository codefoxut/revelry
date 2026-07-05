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
    game_type: "mafia",
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
  it("resets round-scoped state when a room_state event enters the night phase", () => {
    captured!.onEvent({
      type: "vote_cast",
      player_id: "p1",
      target_player_id: "p2",
    });
    expect(useRoomStore.getState().votes).toEqual({ p1: "p2" });

    captured!.onEvent({
      type: "room_state",
      room: baseRoom({ phase: "in_game", game_state: { phase: "night", round_number: 1, alive_player_ids: ["p1", "p2"] } }),
    });

    const state = useRoomStore.getState();
    expect(state.votes).toEqual({});
    expect(state.nightResult).toBeNull();
    expect(state.eliminationResult).toBeNull();
    expect(state.investigationResult).toBeNull();
    expect(state.mafiaPicks).toEqual([]);
    expect(state.room?.game_state?.phase).toBe("night");
  });

  it("stores the live mafia_night_picks snapshot and resets it on a new night", () => {
    captured!.onEvent({
      type: "mafia_night_picks",
      picks: [{ player_id: "p1", target_player_id: "p2", locked: false }],
    });
    expect(useRoomStore.getState().mafiaPicks).toEqual([
      { player_id: "p1", target_player_id: "p2", locked: false },
    ]);

    captured!.onEvent({
      type: "room_state",
      room: baseRoom({ phase: "in_game", game_state: { phase: "night", round_number: 2, alive_player_ids: ["p1", "p2"] } }),
    });

    expect(useRoomStore.getState().mafiaPicks).toEqual([]);
  });

  it("updates only the targeted player's connected flag", () => {
    captured!.onEvent({ type: "room_state", room: baseRoom() });

    captured!.onEvent({ type: "player_connection_changed", player_id: "p2", connected: false });

    const players = useRoomStore.getState().room!.players;
    expect(players.find((p) => p.id === "p2")!.connected).toBe(false);
    expect(players.find((p) => p.id === "p1")!.connected).toBe(true);
  });

  it("accumulates vote_cast events into the votes record", () => {
    captured!.onEvent({ type: "vote_cast", player_id: "p1", target_player_id: "p2" });
    captured!.onEvent({ type: "vote_cast", player_id: "p2", target_player_id: "p1" });

    expect(useRoomStore.getState().votes).toEqual({ p1: "p2", p2: "p1" });
  });

  it("sets the kicked flag on a kicked event", () => {
    expect(useRoomStore.getState().kicked).toBe(false);

    captured!.onEvent({ type: "kicked" });

    expect(useRoomStore.getState().kicked).toBe(true);
  });

  it("sets nightTimer on night_timer_started", () => {
    const before = Date.now();
    captured!.onEvent({ type: "night_timer_started", duration_seconds: 60 });

    const nightTimer = useRoomStore.getState().nightTimer;
    expect(nightTimer).not.toBeNull();
    expect(nightTimer!.durationSeconds).toBe(60);
    expect(nightTimer!.deadlineAt).toBeGreaterThanOrEqual(before + 60_000);
  });

  it("clears nightTimer when room_state reports a non-night phase", () => {
    captured!.onEvent({ type: "night_timer_started", duration_seconds: 60 });
    expect(useRoomStore.getState().nightTimer).not.toBeNull();

    captured!.onEvent({
      type: "room_state",
      room: baseRoom({ phase: "in_game", game_state: { phase: "day", round_number: 1, alive_player_ids: ["p1", "p2"] } }),
    });

    expect(useRoomStore.getState().nightTimer).toBeNull();
  });

  it("stores the winning team and full role reveal on game_over", () => {
    captured!.onEvent({
      type: "game_over",
      winning_team: "town",
      roles: [
        { player_id: "p1", role_key: "mafia", role_display_name: "Mafia", team: "mafia" },
        { player_id: "p2", role_key: "villager", role_display_name: "Villager", team: "town" },
      ],
    });

    const gameOver = useRoomStore.getState().gameOver;
    expect(gameOver).not.toBeNull();
    expect(gameOver!.winningTeam).toBe("town");
    expect(gameOver!.roles).toEqual([
      { playerId: "p1", roleKey: "mafia", roleDisplayName: "Mafia", team: "mafia" },
      { playerId: "p2", roleKey: "villager", roleDisplayName: "Villager", team: "town" },
    ]);
  });

  it("keeps nightTimer when room_state reports the night phase", () => {
    captured!.onEvent({ type: "night_timer_started", duration_seconds: 60 });
    const scheduled = useRoomStore.getState().nightTimer;

    captured!.onEvent({
      type: "room_state",
      room: baseRoom({ phase: "in_game", game_state: { phase: "night", round_number: 1, alive_player_ids: ["p1", "p2"] } }),
    });

    expect(useRoomStore.getState().nightTimer).toEqual(scheduled);
  });
});
