import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

interface LastJudged {
  playerId: string;
  correct: boolean;
  scoreDelta: number;
}

interface GameOverResult {
  scores: Record<string, number>;
  winnerId: string | null;
}

interface RoomStoreState {
  room: Room | null;
  selfPlayerId: string | null;
  lastJudged: LastJudged | null;
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
  lastJudged: null,
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
          case "question_shown":
          case "player_buzzed":
          case "answer_revealed":
            // Fully reflected in the room_state broadcast that follows right
            // after, so there's nothing additional to cache here.
            break;
          case "answer_judged":
            // Transient — used to flash a "Correct!"/"Incorrect" indicator
            // before the next room_state (with updated scores) lands.
            set({
              lastJudged: {
                playerId: event.player_id,
                correct: event.correct,
                scoreDelta: event.score_delta,
              },
            });
            break;
          case "game_over":
            // winner_id isn't part of GameStateOut, so it has to be cached
            // from this event rather than read off room.game_state.
            set({ gameOver: { scores: event.scores, winnerId: event.winner_id } });
            break;
          case "pong":
            break;
        }
      },
    });

    set({
      room: null,
      selfPlayerId: playerId,
      lastJudged: null,
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
