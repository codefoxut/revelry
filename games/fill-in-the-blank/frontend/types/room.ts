export interface Player {
  id: string;
  display_name: string;
  avatar: string;
  is_host: boolean;
  is_ready: boolean;
  is_spectator: boolean;
  connected: boolean;
}

export interface Submission {
  submission_id: string;
  text: string;
}

export interface VoteResult {
  submission_id: string;
  text: string;
  author_id: string;
  votes: number;
}

export interface GameState {
  phase: string;
  question_number: number;
  total_questions: number;
  prompt: string | null;
  submitted_count: number;
  submissions: Submission[] | null;
  voted_count: number;
  results: VoteResult[] | null;
  scores: Record<string, number>;
}

export interface Room {
  code: string;
  game_type: string;
  is_private: boolean;
  phase: string;
  max_players: number;
  players: Player[];
  invite_url: string;
  game_state: GameState | null;
}

export interface RoomSummary {
  code: string;
  game_type: string;
  phase: string;
  is_private: boolean;
  player_count: number;
  max_players: number;
}

export interface CreateRoomResponse {
  room: Room;
  player_id: string;
}
