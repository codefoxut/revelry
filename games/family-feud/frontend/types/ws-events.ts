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

export interface QuestionShownEvent {
  type: "question_shown";
  round_number: number;
  total_rounds: number;
  prompt: string;
  answer_count: number;
}

export interface PlayerBuzzedEvent {
  type: "player_buzzed";
  player_id: string;
  team: "a" | "b";
}

export interface SlotRevealedEvent {
  type: "slot_revealed";
  slot_index: number;
  text: string;
  points: number;
}

export interface StrikeEvent {
  type: "strike";
  team: "a" | "b";
  strikes: number;
}

export interface StealPhaseEvent {
  type: "steal_phase";
  stealing_team: "a" | "b";
}

export interface RoundOverEvent {
  type: "round_over";
  team_awarded: "a" | "b" | null;
  points: number;
  board: { text: string; points: number }[];
}

export interface GameOverEvent {
  type: "game_over";
  team_scores: Record<"a" | "b", number>;
  winning_team: "a" | "b" | null;
}

export type ServerEvent =
  | RoomStateEvent
  | PlayerConnectionChangedEvent
  | ErrorEvent
  | PongEvent
  | KickedEvent
  | QuestionShownEvent
  | PlayerBuzzedEvent
  | SlotRevealedEvent
  | StrikeEvent
  | StealPhaseEvent
  | RoundOverEvent
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

export interface JoinTeamCommand {
  type: "join_team";
  team: "a" | "b";
}

export interface StartGameCommand {
  type: "start_game";
}

export interface BuzzInCommand {
  type: "buzz_in";
}

export interface RevealSlotCommand {
  type: "reveal_slot";
  slot_index: number;
}

export interface StrikeCommand {
  type: "strike";
}

export interface StealRevealCommand {
  type: "steal_reveal";
  slot_index: number;
}

export interface StealMissCommand {
  type: "steal_miss";
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
  | JoinTeamCommand
  | StartGameCommand
  | BuzzInCommand
  | RevealSlotCommand
  | StrikeCommand
  | StealRevealCommand
  | StealMissCommand
  | NextRoundCommand;
