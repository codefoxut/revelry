import { WS_BASE_URL } from "@/lib/config";
import type { ClientCommand, ServerEvent } from "@/types/ws-events";

interface RoomSocketHandlers {
  onEvent: (event: ServerEvent) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
}

/**
 * Thin typed wrapper around the native WebSocket for a single room
 * connection. Reconnect/backoff behavior belongs to a later "reconnection"
 * step — this just opens one socket and reports what happens to it.
 */
export class RoomSocket {
  private ws: WebSocket | null = null;

  constructor(
    private readonly roomCode: string,
    private readonly playerId: string,
    private readonly handlers: RoomSocketHandlers,
  ) {}

  connect(): void {
    const url = `${WS_BASE_URL}/ws/${this.roomCode}?player_id=${encodeURIComponent(this.playerId)}`;
    const ws = new WebSocket(url);

    ws.onopen = () => this.handlers.onOpen?.();
    ws.onclose = (event) => this.handlers.onClose?.(event);
    ws.onmessage = (event) => {
      const parsed = JSON.parse(event.data) as ServerEvent;
      this.handlers.onEvent(parsed);
    };

    this.ws = ws;
  }

  send(command: ClientCommand): void {
    this.ws?.send(JSON.stringify(command));
  }

  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
