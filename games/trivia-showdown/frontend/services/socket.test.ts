import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RoomSocket } from "./socket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  // Real sockets deliver a close event asynchronously even for a
  // caller-initiated close, so the fake mirrors that by firing onclose here.
  close() {
    this.onclose?.({ code: 1000 });
  }
}

function latestSocket(): FakeWebSocket {
  return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("RoomSocket", () => {
  it("retries an unexpected close with exponential backoff", () => {
    const onReconnecting = vi.fn();
    const socket = new RoomSocket("ABCDE", "player-1", { onEvent: vi.fn(), onReconnecting });
    socket.connect();

    expect(FakeWebSocket.instances).toHaveLength(1);

    latestSocket().onclose?.({ code: 1006 });
    expect(onReconnecting).toHaveBeenNthCalledWith(1, 1);

    vi.advanceTimersByTime(999);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    latestSocket().onclose?.({ code: 1006 });
    expect(onReconnecting).toHaveBeenNthCalledWith(2, 2);

    vi.advanceTimersByTime(1999);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it("does not retry after an intentional close() call", () => {
    const onReconnecting = vi.fn();
    const socket = new RoomSocket("ABCDE", "player-1", { onEvent: vi.fn(), onReconnecting });
    socket.connect();

    socket.close();

    vi.advanceTimersByTime(60_000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(onReconnecting).not.toHaveBeenCalled();
  });

  it("does not retry when the server sends a permanent close code", () => {
    const onReconnecting = vi.fn();
    const socket = new RoomSocket("ABCDE", "player-1", { onEvent: vi.fn(), onReconnecting });
    socket.connect();

    latestSocket().onclose?.({ code: 4403 });

    vi.advanceTimersByTime(60_000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(onReconnecting).not.toHaveBeenCalled();
  });

  it("resets the retry counter after a successful reconnect", () => {
    const onReconnecting = vi.fn();
    const socket = new RoomSocket("ABCDE", "player-1", { onEvent: vi.fn(), onReconnecting });
    socket.connect();

    latestSocket().onclose?.({ code: 1006 });
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);

    latestSocket().onopen?.();

    latestSocket().onclose?.({ code: 1006 });
    expect(onReconnecting).toHaveBeenLastCalledWith(1);
  });
});
