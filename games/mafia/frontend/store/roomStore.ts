import { create } from "zustand";
import { RoomSocket } from "@/services/socket";
import type { Room } from "@/types/room";
import type { ClientCommand, RoleOut } from "@/types/ws-events";

type ConnectionStatus = "idle" | "connecting" | "connected" | "closed";

interface NightResult {
  eliminatedPlayerId: string | null;
}

interface EliminationResult {
  eliminatedPlayerId: string | null;
}

interface GameOverResult {
  winningTeam: string;
}

interface InvestigationResult {
  targetPlayerId: string;
  team: string;
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

  connect: (roomCode, playerId) => {
    get().socket?.close();

    const socket = new RoomSocket(roomCode, playerId, {
      onOpen: () => set({ status: "connected" }),
      onClose: (event) => set({ status: "closed", closeCode: event.code }),
      onEvent: (event) => {
        switch (event.type) {
          case "room_state": {
            const startingNewRound = event.room.game_state?.phase === "night";
            set({
              room: event.room,
              ...(startingNewRound
                ? { nightResult: null, eliminationResult: null, investigationResult: null, votes: {} }
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
            set({ gameOver: { winningTeam: event.winning_team } });
            break;
          case "vote_cast":
            set((state) => ({ votes: { ...state.votes, [event.player_id]: event.target_player_id } }));
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
