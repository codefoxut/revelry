function browserHostname(): string | null {
  if (typeof window === "undefined") return null;
  return window.location.hostname || null;
}

function browserProtocol(): string | null {
  if (typeof window === "undefined") return null;
  return window.location.protocol;
}

export function apiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  const hostname = browserHostname();
  if (hostname) {
    const protocol = browserProtocol() === "https:" ? "https:" : "http:";
    return `${protocol}//${hostname}:8000`;
  }

  return "http://localhost:8000";
}

export function wsBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_BASE_URL) {
    return process.env.NEXT_PUBLIC_WS_BASE_URL;
  }

  const hostname = browserHostname();
  if (hostname) {
    const protocol = browserProtocol() === "https:" ? "wss:" : "ws:";
    return `${protocol}//${hostname}:8000`;
  }

  return "ws://localhost:8000";
}
