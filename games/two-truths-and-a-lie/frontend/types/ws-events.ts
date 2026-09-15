import type { Room } from "./room";

// ---- Server -> Client ----

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

export interface RoundStartedEvent {
  type: "round_started";
  storyteller_id: string;
}

export interface StatementsSubmittedEvent {
  type: "statements_submitted";
  statements: string[];
}

export interface PlayerVotedEvent {
  type: "player_voted";
  player_id: string;
}

export interface RevealedEvent {
  type: "revealed";
  lie_index: number;
  correct_voters: string[];
  scores_delta: Record<string, number>;
}

export interface GameOverEvent {
  type: "game_over";
  scores: Record<string, number>;
}

export type ServerEvent =
  | RoomStateEvent
  | PlayerConnectionChangedEvent
  | ErrorEvent
  | PongEvent
  | KickedEvent
  | RoundStartedEvent
  | StatementsSubmittedEvent
  | PlayerVotedEvent
  | RevealedEvent
  | GameOverEvent;

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

export interface SubmitStatementsCommand {
  type: "submit_statements";
  statements: string[];
  lie_index: number;
}

export interface CastVoteCommand {
  type: "cast_vote";
  choice_index: number;
}

export interface RevealCommand {
  type: "reveal";
}

export interface NextRoundCommand {
  type: "next_round";
}

export type ClientCommand =
  | PingCommand
  | SetReadyCommand
  | UpdateProfileCommand
  | KickPlayerCommand
  | LeaveRoomCommand
  | StartGameCommand
  | SubmitStatementsCommand
  | CastVoteCommand
  | RevealCommand
  | NextRoundCommand;
