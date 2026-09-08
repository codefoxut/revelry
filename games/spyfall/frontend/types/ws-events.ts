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

export interface RoleAssignedEvent {
  type: "role_assigned";
  is_spy: boolean;
  location: string | null;
  role: string | null;
}

export interface VoteCastEvent {
  type: "vote_cast";
  player_id: string;
  target_player_id: string;
}

export interface PlayerRoleRevealOut {
  player_id: string;
  is_spy: boolean;
  role: string | null;
}

export interface GameOverEvent {
  type: "game_over";
  winning_side: string;
  location: string;
  spy_player_ids: string[];
  accused_player_id: string | null;
  reveals: PlayerRoleRevealOut[];
}

export interface DiscussionTimerStartedEvent {
  type: "discussion_timer_started";
  duration_seconds: number;
}

export type ServerEvent =
  | RoomStateEvent
  | PlayerConnectionChangedEvent
  | ErrorEvent
  | PongEvent
  | KickedEvent
  | RoleAssignedEvent
  | VoteCastEvent
  | GameOverEvent
  | DiscussionTimerStartedEvent;

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
  enabled_location_keys?: string[] | null;
}

export interface AdvancePhaseCommand {
  type: "advance_phase";
}

export interface CastVoteCommand {
  type: "cast_vote";
  target_player_id: string;
}

export interface GuessLocationCommand {
  type: "guess_location";
  location_key: string;
}

export type ClientCommand =
  | PingCommand
  | SetReadyCommand
  | UpdateProfileCommand
  | KickPlayerCommand
  | LeaveRoomCommand
  | StartGameCommand
  | AdvancePhaseCommand
  | CastVoteCommand
  | GuessLocationCommand;
