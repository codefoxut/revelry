import { WS_BASE_URL } from "@/lib/config";
import type { ClientCommand, ServerEvent } from "@/types/ws-events";

interface RoomSocketHandlers {
  onEvent: (event: ServerEvent) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onReconnecting?: (attempt: number) => void;
}

const MAX_RETRIES = 8;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 10000;

// Close codes >= 4000 are the app's reserved range (see backend `ws.py` /
// `dispatcher.py`) and always mean a permanent, non-retryable outcome —
// kicked (4403) or the room/player no longer existing (4404).
const PERMANENT_CLOSE_CODE_FLOOR = 4000;

/**
 * Thin typed wrapper around the native WebSocket for a single room
 * connection. Automatically retries an unexpected drop with exponential
 * backoff, unless the socket was closed on purpose (via `close()`) or the
 * server closed it with a reserved "don't retry" code.
 */
export class RoomSocket {
  private ws: WebSocket | null = null;
  private intentionalClose = false;
  private retryCount = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly roomCode: string,
    private readonly playerId: string,
    private readonly handlers: RoomSocketHandlers,
  ) {}

  connect(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }

    const url = `${WS_BASE_URL}/ws/${this.roomCode}?player_id=${encodeURIComponent(this.playerId)}`;
    const ws = new WebSocket(url);

    ws.onopen = () => {
      this.retryCount = 0;
      this.handlers.onOpen?.();
    };
    ws.onclose = (event) => {
      this.handlers.onClose?.(event);
      if (this.intentionalClose || event.code >= PERMANENT_CLOSE_CODE_FLOOR) {
        return;
      }
      if (this.retryCount >= MAX_RETRIES) {
        return;
      }

      const attempt = this.retryCount + 1;
      this.retryCount = attempt;
      const delay = Math.min(BASE_DELAY_MS * 2 ** (attempt - 1), MAX_DELAY_MS);
      this.handlers.onReconnecting?.(attempt);
      this.retryTimer = setTimeout(() => this.connect(), delay);
    };
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
    this.intentionalClose = true;
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}
