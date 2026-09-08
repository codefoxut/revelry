import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand, PlayerRoleRevealOut } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

interface MyRole {
  isSpy: boolean;
  location: string | null;
  role: string | null;
}

interface GameOverResult {
  winningSide: string;
  location: string;
  spyPlayerIds: string[];
  accusedPlayerId: string | null;
  reveals: PlayerRoleRevealOut[];
}

interface DiscussionTimer {
  durationSeconds: number;
  deadlineAt: number;
}

interface RoomStoreState {
  room: Room | null;
  selfPlayerId: string | null;
  myRole: MyRole | null;
  status: ConnectionStatus;
  closeCode: number | null;
  kicked: boolean;
  lastError: { code: string; message: string } | null;
  socket: RoomSocket | null;
  votes: Record<string, string>;
  discussionTimer: DiscussionTimer | null;
  gameOver: GameOverResult | null;
  connect: (roomCode: string, playerId: string) => void;
  disconnect: () => void;
  sendCommand: (command: ClientCommand) => void;
}

export const useRoomStore = create<RoomStoreState>((set, get) => ({
  room: null,
  selfPlayerId: null,
  myRole: null,
  status: "idle",
  closeCode: null,
  kicked: false,
  lastError: null,
  socket: null,
  votes: {},
  discussionTimer: null,
  gameOver: null,

  connect: (roomCode, playerId) => {
    get().socket?.close();

    const socket = new RoomSocket(roomCode, playerId, {
      onOpen: () => set({ status: "connected" }),
      onClose: (event) => set({ status: "closed", closeCode: event.code }),
      onReconnecting: () => set({ status: "reconnecting" }),
      onEvent: (event) => {
        switch (event.type) {
          case "room_state": {
            // Votes and the discussion timer are scoped to a single
            // DISCUSSION/VOTING round — reset them whenever the server
            // reports we've entered a fresh discussion window (start_game,
            // or moving past game_over into a new round).
            const enteringDiscussion = event.room.game_state?.phase === "discussion";
            set({
              room: event.room,
              ...(enteringDiscussion
                ? { votes: {}, discussionTimer: null, gameOver: null }
                : {}),
            });
            break;
          }
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
          case "role_assigned":
            // Sent once at game start (and again on reconnect) — cache it
            // for the whole round.
            set({ myRole: { isSpy: event.is_spy, location: event.location, role: event.role } });
            break;
          case "vote_cast":
            set((state) => ({ votes: { ...state.votes, [event.player_id]: event.target_player_id } }));
            break;
          case "discussion_timer_started":
            set({
              discussionTimer: {
                durationSeconds: event.duration_seconds,
                deadlineAt: Date.now() + event.duration_seconds * 1000,
              },
            });
            break;
          case "game_over":
            set({
              gameOver: {
                winningSide: event.winning_side,
                location: event.location,
                spyPlayerIds: event.spy_player_ids,
                accusedPlayerId: event.accused_player_id,
                reveals: event.reveals,
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
      myRole: null,
      status: "connecting",
      closeCode: null,
      kicked: false,
      lastError: null,
      socket,
      votes: {},
      discussionTimer: null,
      gameOver: null,
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
