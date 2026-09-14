const KEY_PREFIX = "revelry:player:";

export function savePlayerId(roomCode: string, playerId: string): void {
  sessionStorage.setItem(`${KEY_PREFIX}${roomCode}`, playerId);
}

export function loadPlayerId(roomCode: string): string | null {
  return sessionStorage.getItem(`${KEY_PREFIX}${roomCode}`);
}

export function clearPlayerId(roomCode: string): void {
  sessionStorage.removeItem(`${KEY_PREFIX}${roomCode}`);
}
