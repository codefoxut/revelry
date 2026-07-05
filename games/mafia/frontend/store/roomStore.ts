import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand, MafiaPickOut, RoleOut } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

interface NightResult {
  eliminatedPlayerId: string | null;
}

interface EliminationResult {
  eliminatedPlayerId: string | null;
}

interface RoleReveal {
  playerId: string;
  roleKey: string;
  roleDisplayName: string;
  team: string;
}

interface GameOverResult {
  winningTeam: string;
  roles: RoleReveal[];
}

interface InvestigationResult {
  targetPlayerId: string;
  team: string;
}

interface NightTimer {
  durationSeconds: number;
  deadlineAt: number;
}

interface RoomStoreState {
  room: Room | null;
  selfPlayerId: string | null;
  myRole: RoleOut | null;
  status: ConnectionStatus;
  closeCode: number | null;
  kicked: boolean;
  lastError: { code: string; message: string } | null;
  socket: RoomSocket | null;
  nightResult: NightResult | null;
  eliminationResult: EliminationResult | null;
  gameOver: GameOverResult | null;
  investigationResult: InvestigationResult | null;
  votes: Record<string, string>;
  mafiaPicks: MafiaPickOut[];
  nightTimer: NightTimer | null;
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
  nightResult: null,
  eliminationResult: null,
  gameOver: null,
  investigationResult: null,
  votes: {},
  mafiaPicks: [],
  nightTimer: null,

  connect: (roomCode, playerId) => {
    get().socket?.close();

    const socket = new RoomSocket(roomCode, playerId, {
      onOpen: () => set({ status: "connected" }),
      onClose: (event) => set({ status: "closed", closeCode: event.code }),
      onReconnecting: () => set({ status: "reconnecting" }),
      onEvent: (event) => {
        switch (event.type) {
          case "room_state": {
            const startingNewRound = event.room.game_state?.phase === "night";
            set({
              room: event.room,
              ...(startingNewRound
                ? {
                    nightResult: null,
                    eliminationResult: null,
                    investigationResult: null,
                    votes: {},
                    mafiaPicks: [],
                  }
                : { nightTimer: null }),
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
            set({ myRole: event.role });
            break;
          case "investigation_result":
            set({ investigationResult: { targetPlayerId: event.target_player_id, team: event.team } });
            break;
          case "night_result":
            set({ nightResult: { eliminatedPlayerId: event.eliminated_player_id } });
            break;
          case "elimination_result":
            set({ eliminationResult: { eliminatedPlayerId: event.eliminated_player_id } });
            break;
          case "game_over":
            set({
              gameOver: {
                winningTeam: event.winning_team,
                roles: event.roles.map((reveal) => ({
                  playerId: reveal.player_id,
                  roleKey: reveal.role_key,
                  roleDisplayName: reveal.role_display_name,
                  team: reveal.team,
                })),
              },
            });
            break;
          case "vote_cast":
            set((state) => ({ votes: { ...state.votes, [event.player_id]: event.target_player_id } }));
            break;
          case "mafia_night_picks":
            set({ mafiaPicks: event.picks });
            break;
          case "night_timer_started":
            set({
              nightTimer: {
                durationSeconds: event.duration_seconds,
                deadlineAt: Date.now() + event.duration_seconds * 1000,
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
      nightResult: null,
      eliminationResult: null,
      gameOver: null,
      investigationResult: null,
      votes: {},
      mafiaPicks: [],
      nightTimer: null,
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
