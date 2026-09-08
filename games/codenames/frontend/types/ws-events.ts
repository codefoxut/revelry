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

export interface TeamAssignedEvent {
  type: "team_assigned";
  team: string;
  role: string;
}

export interface SpymasterViewEvent {
  type: "spymaster_view";
  colors: string[];
}

export interface ClueGivenEvent {
  type: "clue_given";
  team: string;
  word: string;
  number: number;
}

export interface CardRevealedEvent {
  type: "card_revealed";
  card_index: number;
  word: string;
  color: string;
  guessed_by: string;
}

export interface GameOverEvent {
  type: "game_over";
  winning_side: string;
  reason: string;
  colors: string[];
}

export type ServerEvent =
  | RoomStateEvent
  | PlayerConnectionChangedEvent
  | ErrorEvent
  | PongEvent
  | KickedEvent
  | TeamAssignedEvent
  | SpymasterViewEvent
  | ClueGivenEvent
  | CardRevealedEvent
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
  word: string;
  number: number;
}

export interface MakeGuessCommand {
  type: "make_guess";
  card_index: number;
}

export interface EndTurnCommand {
  type: "end_turn";
}

export type ClientCommand =
  | PingCommand
  | SetReadyCommand
  | UpdateProfileCommand
  | KickPlayerCommand
  | LeaveRoomCommand
  | StartGameCommand
  | GiveClueCommand
  | MakeGuessCommand
  | EndTurnCommand;
