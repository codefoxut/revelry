import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

interface RoomStoreState {
  room: Room | null;
  selfPlayerId: string | null;
  /** The psychic's secret target (0–100). Only populated for the current Psychic — null for everyone else. */
  psychicSecret: number | null;
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
  psychicSecret: null,
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
          case "psychic_target":
            // Sent ONLY to the current Psychic — populate the secret target.
            // Never set a default value for non-Psychics (they simply never receive this).
            set({ psychicSecret: event.target_position });
            break;
          case "clue_given":
          case "player_guessed":
          case "revealed":
            // All reflected in the room_state broadcast that follows right after.
            break;
          case "game_over":
            // Scores reflected in the room_state broadcast.
            break;
          case "pong":
            break;
        }
      },
    });

    set({
      room: null,
      selfPlayerId: playerId,
      psychicSecret: null,
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
