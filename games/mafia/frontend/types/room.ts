export interface Player {
  id: string;
  display_name: string;
  avatar: string;
  is_host: boolean;
  is_ready: boolean;
  is_spectator: boolean;
  connected: boolean;
}

export interface Room {
  code: string;
  game_type: string;
  is_private: boolean;
  phase: string;
  max_players: number;
  players: Player[];
  invite_url: string;
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
