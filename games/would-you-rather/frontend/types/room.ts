export interface Player {
  id: string;
  display_name: string;
  avatar: string;
  is_host: boolean;
  is_ready: boolean;
  is_spectator: boolean;
  connected: boolean;
}

export interface RecapEntry {
  option_a: string;
  option_b: string;
  votes: Record<string, "a" | "b">;
}

export interface GameState {
  phase: "lobby" | "question_open" | "revealed" | "game_over";
  round_number: number;
  total_questions: number;
  option_a: string | null;
  option_b: string | null;
  voted: string[];
  revealed_votes: Record<string, string> | null;
  recap: RecapEntry[] | null;
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
