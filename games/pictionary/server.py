import json
import os
import random
import anthropic
import tornado.ioloop
import tornado.web
import tornado.options
from tornado.options import define, options

import pictionary_db

define("port", default=9090, help="run on the given port", type=int)
define("debug", default=False, help="run in debug mode", type=bool)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

db_conn = pictionary_db.get_connection()

# Shared async Anthropic client (reused across requests)
_claude = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

# Online mode is only offered to the client when a key is actually configured
ONLINE_AVAILABLE = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

# ---------------------------------------------------------------------------
# Standard Pictionary Prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are a Pictionary game master crafting cards for a lively party game.
Your job: generate a set of drawable items for a given category.

Golden rules for Pictionary items:
1. DRAWABLE — players must be able to sketch it in under 60 seconds.
2. GUESSABLE — teammates can recognise it from a quick sketch alone.
3. CONCRETE — prefer specific nouns or vivid action scenes over vague abstractions.
4. VARIED DIFFICULTY — mix at least one easy item with harder ones.
5. FUN & SURPRISING — avoid the most obvious, overused choices when you can.

Output format: valid JSON array of strings, nothing else — no markdown, no prose."""

_USER_PROMPT_TEMPLATE = """\
Category: {category}
Number of items: {n}

Generate exactly {n} Pictionary items for this category.
Return ONLY a JSON array, e.g.: ["item one", "item two", "item three"]"""


def _fallback_items(category: dict, n: int) -> list[str]:
    """Return n random items from the static data when Claude is unavailable."""
    pool = pictionary_db.random_items(db_conn, category["id"], n)
    return pool if pool else [category["name"]]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def write_json(self, data):
        self.write(json.dumps(data))

    def write_error_json(self, status, message):
        self.set_status(status)
        self.write(json.dumps({"error": message}))


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        # Serve as a raw file — Tornado's template engine would conflict
        # with Vue.js's {{ }} mustache syntax.
        self.set_header("Content-Type", "text/html; charset=UTF-8")
        with open(os.path.join(BASE_DIR, "templates", "index.html"), "rb") as f:
            self.write(f.read())


class ConfigHandler(BaseHandler):
    def get(self):
        self.write_json({"online_available": ONLINE_AVAILABLE})


class CategoriesHandler(BaseHandler):
    def get(self):
        self.write_json({"categories": pictionary_db.list_categories(db_conn)})


class CardHandler(BaseHandler):
    async def post(self):
        try:
            body = json.loads(self.request.body)
        except json.JSONDecodeError:
            self.write_error_json(400, "Invalid JSON body")
            return

        category_id = body.get("category_id", "").strip()
        if not category_id:
            self.write_error_json(400, "category_id is required")
            return

        category = pictionary_db.get_category(db_conn, category_id)
        if not category:
            self.write_error_json(404, f"Category '{category_id}' not found")
            return

        requested_mode = body.get("mode", "online")
        use_online = requested_mode == "online" and ONLINE_AVAILABLE

        num_options = random.randint(3, 4)
        items = await self._generate_items(category, num_options, use_online)

        self.write_json(
            {
                "category_id": category["id"],
                "category_name": category["name"],
                "category_emoji": category["emoji"],
                "category_color": category["color"],
                "items": items,
            }
        )

    async def _generate_items(self, category: dict, n: int, use_online: bool) -> list[str]:
        """Ask Claude to generate n Pictionary items for the category.

        Offline mode skips Claude entirely. Online mode keeps the existing
        try/except so a network hiccup or rate limit falls back to the
        static DB silently (no user-facing error).
        """
        if not use_online:
            return _fallback_items(category, n)

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            category=category["name"], n=n
        )
        try:
            message = await _claude.messages.create(
                model="claude-haiku-4-5",
                max_tokens=256,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = message.content[0].text.strip()
            items = json.loads(raw)
            if isinstance(items, list) and all(isinstance(x, str) for x in items):
                return items[:n]
        except Exception as exc:
            print(f"[Claude] Card generation failed ({type(exc).__name__}): {exc}")

        # Graceful fallback to static data when Claude is unavailable
        return _fallback_items(category, n)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def make_app(debug: bool = False) -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/api/config", ConfigHandler),
            (r"/api/categories", CategoriesHandler),
            (r"/api/card", CardHandler),
        ],
        debug=debug,
        autoreload=debug,
    )


if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = make_app(debug=options.debug)
    app.listen(options.port)
    print(f"\n🎨  Pictionary is live at  http://localhost:{options.port}\n")
    print("   Cards generated by Claude Haiku — set ANTHROPIC_API_KEY in env.\n")
    tornado.ioloop.IOLoop.current().start()
