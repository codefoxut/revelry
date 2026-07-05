#!/usr/bin/env python3
"""Revelry games hub — a landing page linking to each game.

Each game runs as its own standalone app on its own port; this just serves a
single page linking to whichever ones are currently running (and how to start
the rest). No third-party dependencies — stdlib only, so there's nothing to
install before running it.

Usage:
    python3 hub.py [--port 4000] [--mafia-port 3000] [--charades-port 8080]
"""

import argparse
import html
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit


def build_games(mafia_port: int, charades_port: int) -> list[dict]:
    return [
        {
            "name": "Mafia",
            "description": "Real-time multiplayer social deduction, browser-based.",
            "url": f"http://localhost:{mafia_port}",
            "path": "games/mafia",
            "start": "cd games/mafia && make install && make dev",
        },
        {
            "name": "Charades",
            "description": "Bollywood-movie charades, single screen, AI-powered clues.",
            "url": f"http://localhost:{charades_port}",
            "path": "games/bollywood-dumbcharades",
            "start": "cd games/bollywood-dumbcharades && make run",
        },
    ]


def is_up(url: str) -> bool:
    parts = urlsplit(url)
    host = parts.hostname or "localhost"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def render_html(games: list[dict]) -> str:
    cards = []
    for game in games:
        online = is_up(game["url"])
        status = (
            '<span class="status online">● running</span>'
            if online
            else '<span class="status offline">○ not running</span>'
        )
        link = (
            f'<a class="play" href="{html.escape(game["url"])}">Play →</a>'
            if online
            else f'<code class="start">{html.escape(game["start"])}</code>'
        )
        cards.append(
            f"""
            <div class="card">
              <div class="card-head">
                <h2>{html.escape(game["name"])}</h2>
                {status}
              </div>
              <p>{html.escape(game["description"])}</p>
              {link}
            </div>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revelry — Games Hub</title>
<meta http-equiv="refresh" content="15">
<style>
  body {{
    margin: 0;
    padding: 3rem 1.5rem;
    background: #09090b;
    color: #fafafa;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  h1 {{ text-align: center; margin-bottom: 0.25rem; }}
  .subtitle {{ text-align: center; color: #a1a1aa; margin-bottom: 2.5rem; }}
  .grid {{
    display: grid;
    gap: 1rem;
    max-width: 640px;
    margin: 0 auto;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  }}
  .card {{
    border: 1px solid #27272a;
    background: #18181b;
    border-radius: 0.75rem;
    padding: 1.25rem;
  }}
  .card-head {{ display: flex; align-items: center; justify-content: space-between; }}
  .card h2 {{ margin: 0; font-size: 1.1rem; }}
  .card p {{ color: #a1a1aa; font-size: 0.875rem; }}
  .status {{ font-size: 0.75rem; }}
  .status.online {{ color: #34d399; }}
  .status.offline {{ color: #71717a; }}
  .play {{
    display: inline-block;
    background: #f43f5e;
    color: white;
    text-decoration: none;
    font-weight: 600;
    padding: 0.5rem 1rem;
    border-radius: 999px;
    font-size: 0.875rem;
  }}
  .start {{
    display: block;
    color: #d4d4d8;
    background: #09090b;
    border: 1px solid #27272a;
    border-radius: 0.5rem;
    padding: 0.5rem 0.75rem;
    font-size: 0.75rem;
    overflow-x: auto;
  }}
</style>
</head>
<body>
  <h1>Revelry</h1>
  <p class="subtitle">Pick a game. Page refreshes every 15s to pick up newly started games.</p>
  <div class="grid">
    {"".join(cards)}
  </div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        body = render_html(self.server.games).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4000, help="port for this hub page")
    parser.add_argument("--mafia-port", type=int, default=3000, help="port Mafia's frontend runs on")
    parser.add_argument("--charades-port", type=int, default=8080, help="port Charades runs on")
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    server.games = build_games(args.mafia_port, args.charades_port)
    print(f"Revelry games hub running at http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
