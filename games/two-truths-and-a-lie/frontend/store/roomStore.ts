import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

interface RevealData {
  lieIndex: number;
  correctVoters: string[];
  scoresDelta: Record<string, number>;
}

interface GameOverResult {
  scores: Record<string, number>;
}

interface RoomStoreState {
  room: Room | null;
  selfPlayerId: string | null;
  revealData: RevealData | null;
  gameOver: GameOverResult | null;
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
  revealData: null,
  gameOver: null,
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
          case "round_started":
          case "statements_submitted":
          case "player_voted":
            // Fully reflected in the room_state broadcast that follows.
            break;
          case "revealed":
            // Cached separately — lie_index and correct_voters come from
            // this event so we have them for the reveal screen.
            set({
              revealData: {
                lieIndex: event.lie_index,
                correctVoters: event.correct_voters,
                scoresDelta: event.scores_delta,
              },
            });
            break;
          case "game_over":
            set({ gameOver: { scores: event.scores } });
            break;
          case "pong":
            break;
        }
      },
    });

    set({
      room: null,
      selfPlayerId: playerId,
      revealData: null,
      gameOver: null,
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
