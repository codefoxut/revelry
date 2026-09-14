import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

interface GameOverResult {
  team_scores: Record<"a" | "b", number>;
  winning_team: "a" | "b" | null;
}

interface RoundOverResult {
  team_awarded: "a" | "b" | null;
  points: number;
  board: { text: string; points: number }[];
}

interface RoomStoreState {
  room: Room | null;
  selfPlayerId: string | null;
  gameOver: GameOverResult | null;
  lastRoundOver: RoundOverResult | null;
  status: ConnectionStatus;
  closeCode: number | null;
  kicked: boolean;
  lastError: { code: string; message: string } | null;
  socket: RoomSocket | null;
  connect: (roomCode: string, playerId: string) => void;
  disconnect: () => void;
  sendCommand: (command: ClientCommand) => void;
}

export const useRoomStore = create<RoomStoreState>((set, get) => ({
  room: null,
  selfPlayerId: null,
  gameOver: null,
  lastRoundOver: null,
  status: "idle",
  closeCode: null,
  kicked: false,
  lastError: null,
  socket: null,

  connect: (roomCode, playerId) => {
    get().socket?.close();

    const socket = new RoomSocket(roomCode, playerId, {
      onOpen: () => set({ status: "connected" }),
      onClose: (event) => set({ status: "closed", closeCode: event.code }),
      onReconnecting: () => set({ status: "reconnecting" }),
      onEvent: (event) => {
        switch (event.type) {
          case "room_state":
            set({ room: event.room });
            break;
          case "player_connection_changed":
            set((state) => {
              if (!state.room) return state;
              return {
                room: {
                  ...state.room,
                  players: state.room.players.map((player) =>
                    player.id === event.player_id
                      ? { ...player, connected: event.connected }
                      : player,
                  ),
                },
              };
            });
            break;
          case "kicked":
            set({ kicked: true });
            break;
          case "error":
            set({ lastError: { code: event.code, message: event.message } });
            break;
          case "round_over":
            // Cache the full board reveal so we can show it during round_over phase.
            set({ lastRoundOver: { team_awarded: event.team_awarded, points: event.points, board: event.board } });
            break;
          case "game_over":
            // winning_team isn't exposed in GameStateOut, so cache it here.
            set({ gameOver: { team_scores: event.team_scores, winning_team: event.winning_team } });
            break;
          case "question_shown":
          case "player_buzzed":
          case "slot_revealed":
          case "strike":
          case "steal_phase":
            // All reflected in the room_state that follows immediately.
            break;
          case "pong":
            break;
        }
      },
    });

    set({
      room: null,
      selfPlayerId: playerId,
      gameOver: null,
      lastRoundOver: null,
      status: "connecting",
      closeCode: null,
      kicked: false,
      lastError: null,
      socket,
    });
    socket.connect();
  },

  disconnect: () => {
    get().socket?.close();
    set({ socket: null, status: "idle" });
  },

  sendCommand: (command) => {
    get().socket?.send(command);
  },
}));
