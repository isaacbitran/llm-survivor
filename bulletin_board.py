"""Public bulletin board shared by all agents."""

import json
import os
from config import DATA_DIR, BULLETIN_BOARD_TOKEN_CAP


def _token_count(text):
    """Approximate token count using word count."""
    return len(text.split())


class BulletinBoard:
    def __init__(self):
        self.filepath = os.path.join(DATA_DIR, "bulletin_board.json")
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.posts = data.get("posts", [])
            self.pending = data.get("pending", [])
        else:
            self.posts = []
            self.pending = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump({"posts": self.posts, "pending": self.pending}, f, indent=2)

    def add_post(self, author, content, day):
        """Add a post to the pending queue (will appear tomorrow)."""
        self.pending.append({
            "author": author,
            "content": content,
            "day": day,
        })
        self._save()

    def deliver_pending(self):
        """Move pending posts to the live board. Called at start of new day."""
        if not self.pending:
            return
        self.posts.extend(self.pending)
        self.pending = []
        self._enforce_token_cap()
        self._save()

    def _enforce_token_cap(self):
        """Remove oldest posts (FIFO) until under token cap."""
        while self._total_tokens() > BULLETIN_BOARD_TOKEN_CAP and self.posts:
            self.posts.pop(0)

    def _total_tokens(self):
        total = 0
        for post in self.posts:
            total += _token_count(f"{post['author']} (day {post['day']}): {post['content']}")
        return total

    def render(self):
        """Render the board for prompt inclusion."""
        if not self.posts:
            return "[The bulletin board is empty.]"
        lines = []
        for post in self.posts:
            lines.append(f"— {post['author'].capitalize()} (day {post['day']}): {post['content']}")
        return "\n".join(lines)

    def get_posts(self):
        """Return a copy of all current posts."""
        return list(self.posts)
