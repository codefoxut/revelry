import type { Room } from "./room";

// ---- Server -> Client ----
// Mirrors app/schemas/ws_events.py on the backend, one interface per `type`.

export interface RoomStateEvent {
  type: "room_state";
  room: Room;
}

export interface PlayerConnectionChangedEvent {
  type: "player_connection_changed";
  player_id: string;
  connected: boolean;
}

export interface ErrorEvent {
  type: "error";
  code: string;
  message: string;
}

export interface PongEvent {
  type: "pong";
}

export interface KickedEvent {
  type: "kicked";
}

export interface RoleOut {
  key: string;
  display_name: string;
  team: string;
  description: string;
  acts_at_night: boolean;
}

export interface RoleAssignedEvent {
  type: "role_assigned";
  role: RoleOut;
}

export type ServerEvent =
  | RoomStateEvent
  | PlayerConnectionChangedEvent
  | ErrorEvent
  | PongEvent
  | KickedEvent
  | RoleAssignedEvent;

// ---- Client -> Server ----

export interface PingCommand {
  type: "ping";
}

export interface SetReadyCommand {
  type: "set_ready";
  ready: boolean;
}

export interface UpdateProfileCommand {
  type: "update_profile";
  display_name?: string;
  avatar?: string;
}

export interface KickPlayerCommand {
  type: "kick_player";
  target_player_id: string;
}

export interface LeaveRoomCommand {
  type: "leave_room";
}

export interface StartGameCommand {
  type: "start_game";
}

export interface AdvancePhaseCommand {
  type: "advance_phase";
}

export type ClientCommand =
  | PingCommand
  | SetReadyCommand
  | UpdateProfileCommand
  | KickPlayerCommand
  | LeaveRoomCommand
  | StartGameCommand
  | AdvancePhaseCommand;
