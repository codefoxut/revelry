import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

interface MyAssignment {
  team: string;
  role: string;
}

interface GameOverResult {
  winningSide: string;
  reason: string;
  colors: string[];
}

interface RoomStoreState {
  room: Room | null;
  selfPlayerId: string | null;
  myAssignment: MyAssignment | null;
  spymasterColors: string[] | null;
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
  myAssignment: null,
  spymasterColors: null,
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
          case "team_assigned":
            // Sent once at game start (and again on reconnect) — cache it
            // for the whole game.
            set({ myAssignment: { team: event.team, role: event.role } });
            break;
          case "spymaster_view":
            // Only ever sent to that room's two spymasters, never broadcast.
            set({ spymasterColors: event.colors });
            break;
          case "clue_given":
          case "card_revealed":
            // Both are reflected in the room_state broadcast that follows
            // right after, so there's nothing additional to cache here.
            break;
          case "game_over":
            set({
              gameOver: {
                winningSide: event.winning_side,
                reason: event.reason,
                colors: event.colors,
              },
            });
            break;
          case "pong":
            break;
        }
      },
    });

    set({
      room: null,
      selfPlayerId: playerId,
      myAssignment: null,
      spymasterColors: null,
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
