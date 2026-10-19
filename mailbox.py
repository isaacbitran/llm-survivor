"""Private mailbox system for agent-to-agent letters."""

import json
import os
from config import DATA_DIR


class Mailbox:
    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.filepath = os.path.join(DATA_DIR, "agents", agent_name, "mailbox.json")
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.letters = data.get("letters", [])
            self.pending = data.get("pending", [])
        else:
            self.letters = []
            self.pending = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump({"letters": self.letters, "pending": self.pending}, f, indent=2)

    def deliver(self, from_name, content, signed, day_sent):
        """Queue a letter for delivery (arrives next morning)."""
        letter = {
            "from": from_name,
            "signed": signed,
            "content": content,
            "day_sent": day_sent,
        }
        self.pending.append(letter)
        self._save()

    def deliver_pending(self):
        """Move pending letters to the inbox. Called at start of new day."""
        if not self.pending:
            return
        self.letters.extend(self.pending)
        self.pending = []
        self._save()

    def collect_and_clear(self):
        """Return all letters in the inbox and clear it. Letters are saved in logs."""
        letters = list(self.letters)
        self.letters = []
        self._save()
        return letters

    @staticmethod
    def render_letters(letters):
        """Render letters for prompt inclusion."""
        if not letters:
            return "[No new letters.]"
        lines = []
        for letter in letters:
            sender = letter["from"] if letter["signed"] else "Anonymous"
            lines.append(f"— From {sender} (day {letter['day_sent']}):\n{letter['content']}")
        return "\n\n".join(lines)
