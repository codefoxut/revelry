export interface Player {
  id: string;
  display_name: string;
  avatar: string;
  is_host: boolean;
  is_ready: boolean;
  is_spectator: boolean;
  connected: boolean;
}

export interface BoardCard {
  word: string;
  revealed: boolean;
  color: string | null;
}

export interface CurrentClue {
  word: string;
  number: number;
  guesses_made: number;
  max_guesses: number;
}

export interface GameState {
  phase: string;
  round_number: number;
  current_team: string | null;
  current_clue: CurrentClue | null;
  board: BoardCard[];
  red_remaining: number;
  blue_remaining: number;
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
