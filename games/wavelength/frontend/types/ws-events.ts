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

export interface PsychicTargetEvent {
  type: "psychic_target";
  /** The hidden target position (0–100). Sent ONLY to the current Psychic. */
  target_position: number;
}

export interface ClueGivenEvent {
  type: "clue_given";
  clue_text: string;
  psychic_id: string;
}

export interface PlayerGuessedEvent {
  type: "player_guessed";
  player_id: string;
  guessed_count: number;
}

export interface RevealedEvent {
  type: "revealed";
  target_position: number;
  guesses: Record<string, number>;
  points_awarded: Record<string, number>;
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
  | PsychicTargetEvent
  | ClueGivenEvent
  | PlayerGuessedEvent
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

export interface GiveClueCommand {
  type: "give_clue";
  clue_text?: string;
}

export interface SubmitGuessCommand {
  type: "submit_guess";
  position: number;
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
  | GiveClueCommand
  | SubmitGuessCommand
  | RevealCommand
  | NextRoundCommand;
