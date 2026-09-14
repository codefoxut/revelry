export interface Player {
  id: string;
  display_name: string;
  avatar: string;
  is_host: boolean;
  is_ready: boolean;
  is_spectator: boolean;
  connected: boolean;
}

export interface GameState {
  phase: string;
  round_number: number;
  total_rounds: number;
  psychic_id: string | null;
  left_label: string;
  right_label: string;
  /** Only populated during reveal (public by then). Null during clue_giving and guessing. */
  target_position: number | null;
  clue_text: string | null;
  guessed_count: number;
  /** Populated only during reveal. */
  guesses: Record<string, number> | null;
  /** Per-player round points. Populated only during reveal. */
  points_awarded: Record<string, number> | null;
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
