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

export interface InvestigationResultEvent {
  type: "investigation_result";
  target_player_id: string;
  team: string;
}

export interface NightResultEvent {
  type: "night_result";
  eliminated_player_id: string | null;
}

export interface EliminationResultEvent {
  type: "elimination_result";
  eliminated_player_id: string | null;
}

export interface RoleRevealOut {
  player_id: string;
  role_key: string;
  role_display_name: string;
  team: string;
}

export interface GameOverEvent {
  type: "game_over";
  winning_team: string;
  roles: RoleRevealOut[];
}

export interface VoteCastEvent {
  type: "vote_cast";
  player_id: string;
  target_player_id: string;
}

export interface MafiaPickOut {
  player_id: string;
  target_player_id: string | null;
  locked: boolean;
}

export interface MafiaNightPicksEvent {
  type: "mafia_night_picks";
  picks: MafiaPickOut[];
}

export interface NightTimerStartedEvent {
  type: "night_timer_started";
  duration_seconds: number;
}

export type ServerEvent =
  | RoomStateEvent
  | PlayerConnectionChangedEvent
  | ErrorEvent
  | PongEvent
  | KickedEvent
  | RoleAssignedEvent
  | InvestigationResultEvent
  | NightResultEvent
  | EliminationResultEvent
  | GameOverEvent
  | VoteCastEvent
  | MafiaNightPicksEvent
  | NightTimerStartedEvent;

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
  conflict_resolution: "kill_any" | "no_kill";
}

export interface AdvancePhaseCommand {
  type: "advance_phase";
}

export interface NightActionCommand {
  type: "night_action";
  target_player_id: string;
}

export interface CastVoteCommand {
  type: "cast_vote";
  target_player_id: string;
}

export interface LockNightActionCommand {
  type: "lock_night_action";
}

export type ClientCommand =
  | PingCommand
  | SetReadyCommand
  | UpdateProfileCommand
  | KickPlayerCommand
  | LeaveRoomCommand
  | StartGameCommand
  | AdvancePhaseCommand
  | NightActionCommand
  | CastVoteCommand
  | LockNightActionCommand;
