#!/usr/bin/env python3
"""Revelry games hub — a landing page linking to each game.

Each game runs as its own standalone app on its own port; this just serves a
single page linking to whichever ones are currently running (and how to start
the rest). No third-party dependencies — stdlib only, so there's nothing to
install before running it.

Usage:
    python3 hub.py [--port 4000] [--mafia-port 3000] [--charades-port 8080] \
        [--guess-the-personality-port 8081]
"""

import argparse
import html
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

TEMPLATES_DIR = Path(__file__).parent / "www" / "templates"


def build_games(mafia_port: int, charades_port: int, guess_the_personality_port: int) -> list[dict]:
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
        {
            "name": "Guess the Personality",
            "description": "AI-powered guess-who, single screen.",
            "url": f"http://localhost:{guess_the_personality_port}",
            "path": "games/guess-the-personality",
            "start": "cd games/guess-the-personality && make run",
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


def render_card(game: dict) -> str:
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
    template = (TEMPLATES_DIR / "card.html").read_text()
    return (
        template.replace("{{NAME}}", html.escape(game["name"]))
        .replace("{{STATUS}}", status)
        .replace("{{DESCRIPTION}}", html.escape(game["description"]))
        .replace("{{LINK}}", link)
    )


def render_html(games: list[dict]) -> str:
    cards = "".join(render_card(game) for game in games)
    template = (TEMPLATES_DIR / "index.html").read_text()
    return template.replace("{{CARDS}}", cards)


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
    parser.add_argument(
        "--guess-the-personality-port",
        type=int,
        default=8081,
        help="port Guess the Personality runs on",
    )
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    server.games = build_games(args.mafia_port, args.charades_port, args.guess_the_personality_port)
    print(f"Revelry games hub running at http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
