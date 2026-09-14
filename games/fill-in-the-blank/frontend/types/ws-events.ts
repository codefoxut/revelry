import type { Room, Submission, VoteResult } from "./room";

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

export interface PromptShownEvent {
  type: "prompt_shown";
  prompt: string;
  question_number: number;
  total_questions: number;
}

export interface PlayerSubmittedEvent {
  type: "player_submitted";
  player_id: string;
}

export interface SubmissionsRevealedEvent {
  type: "submissions_revealed";
  submissions: Submission[];
}

export interface PlayerVotedEvent {
  type: "player_voted";
  player_id: string;
}

export interface VoteResultsEvent {
  type: "vote_results";
  results: VoteResult[];
}

export interface RoundOverEvent {
  type: "round_over";
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
  | PromptShownEvent
  | PlayerSubmittedEvent
  | SubmissionsRevealedEvent
  | PlayerVotedEvent
  | VoteResultsEvent
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

export interface StartGameCommand {
  type: "start_game";
}

export interface SubmitAnswerCommand {
  type: "submit_answer";
  text: string;
}

export interface RevealCommand {
  type: "reveal";
}

export interface StartVoteCommand {
  type: "start_vote";
}

export interface CastVoteCommand {
  type: "cast_vote";
  submission_id: string;
}

export interface NextPromptCommand {
  type: "next_prompt";
}

export type ClientCommand =
  | PingCommand
  | SetReadyCommand
  | UpdateProfileCommand
  | KickPlayerCommand
  | LeaveRoomCommand
  | StartGameCommand
  | SubmitAnswerCommand
  | RevealCommand
  | StartVoteCommand
  | CastVoteCommand
  | NextPromptCommand;
