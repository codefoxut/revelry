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

export interface QuestionShownEvent {
  type: "question_shown";
  question_number: number;
  total_questions: number;
  category: string;
  question: string;
}

export interface PlayerBuzzedEvent {
  type: "player_buzzed";
  player_id: string;
}

export interface AnswerJudgedEvent {
  type: "answer_judged";
  player_id: string;
  correct: boolean;
  score_delta: number;
}

export interface AnswerRevealedEvent {
  type: "answer_revealed";
  answer: string;
}

export interface GameOverEvent {
  type: "game_over";
  scores: Record<string, number>;
  winner_id: string | null;
}

export type ServerEvent =
  | RoomStateEvent
  | PlayerConnectionChangedEvent
  | ErrorEvent
  | PongEvent
  | KickedEvent
  | QuestionShownEvent
  | PlayerBuzzedEvent
  | AnswerJudgedEvent
  | AnswerRevealedEvent
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

export interface BuzzInCommand {
  type: "buzz_in";
}

export interface JudgeAnswerCommand {
  type: "judge_answer";
  correct: boolean;
}

export interface RevealCommand {
  type: "reveal";
}

export interface NextQuestionCommand {
  type: "next_question";
}

export type ClientCommand =
  | PingCommand
  | SetReadyCommand
  | UpdateProfileCommand
  | KickPlayerCommand
  | LeaveRoomCommand
  | StartGameCommand
  | BuzzInCommand
  | JudgeAnswerCommand
  | RevealCommand
  | NextQuestionCommand;
