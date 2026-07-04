import { API_BASE_URL } from "@/lib/config";
import type { CreateRoomResponse, RoomSummary } from "@/types/room";

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function createRoom(hostDisplayName: string): Promise<CreateRoomResponse> {
  const response = await fetch(`${API_BASE_URL}/api/rooms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_type: "mafia", host_display_name: hostDisplayName }),
  });
  return parseOrThrow<CreateRoomResponse>(response);
}

export async function joinRoom(code: string, displayName: string): Promise<CreateRoomResponse> {
  const response = await fetch(`${API_BASE_URL}/api/rooms/${code}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName }),
  });
  return parseOrThrow<CreateRoomResponse>(response);
}

export async function getRoomSummary(code: string): Promise<RoomSummary> {
  const response = await fetch(`${API_BASE_URL}/api/rooms/${code}`);
  return parseOrThrow<RoomSummary>(response);
}
