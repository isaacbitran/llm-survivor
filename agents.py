"""Agent, Journal, and game state management."""

import json
import os
import re
from config import (
    DATA_DIR, build_system_prompt,
    JOURNAL_TOKEN_CAP, JOURNAL_COMPRESSION_TARGET,
    JOURNAL_ENTRY_MAX_TOKENS, JOURNAL_TIERS, MAX_TOKENS,
)
from mailbox import Mailbox
from api_client import call_personality


def _token_count(text):
    return len(text.split())


class Journal:
    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.filepath = os.path.join(DATA_DIR, "agents", agent_name, "journal.txt")
        self._entries = []
        self._load()

    def _load(self):
        if not os.path.exists(self.filepath):
            self._entries = []
            return
        with open(self.filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            self._entries = []
            return
        parts = re.split(r'(=== Day \d+ ===)', content)
        self._entries = []
        i = 0
        while i < len(parts):
            part = parts[i].strip()
            if part.startswith("=== Day"):
                header = part
                body = parts[i + 1].strip() if i + 1 < len(parts) else ""
                self._entries.append(f"{header}\n{body}")
                i += 2
            else:
                if part:
                    self._entries.append(part)
                i += 1

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write("\n\n".join(self._entries))

    def read(self):
        return "\n\n".join(self._entries)

    def get_for(self, call_type):
        tier = JOURNAL_TIERS.get(call_type, "full")
        if tier == "last_3":
            entries = self._entries[-3:] if len(self._entries) > 3 else self._entries
        else:
            entries = self._entries
        return "\n\n".join(entries) if entries else "[Your journal is empty. This is your first day.]"

    def get_latest_entry(self):
        if not self._entries:
            return "[Their journal is empty.]"
        return self._entries[-1]

    def append_entry(self, day, text):
        # Strip agent-generated day/journal headers (e.g. "# Journal — Day 3", "# Day 2 — Journal")
        text = re.sub(r'^#+ .*(?:day|journal).*\n*', '', text, count=1, flags=re.IGNORECASE).strip()
        words = text.split()
        if len(words) > JOURNAL_ENTRY_MAX_TOKENS:
            words = words[:JOURNAL_ENTRY_MAX_TOKENS]
            text = " ".join(words)
        day_header = f"=== Day {day} ==="
        found = False
        for i, entry in enumerate(self._entries):
            if entry.startswith(day_header):
                self._entries[i] = f"{self._entries[i]}\n{text}"
                found = True
                break
        if not found:
            self._entries.append(f"{day_header}\n{text}")
        self._save()

    def needs_compression(self):
        return _token_count(self.read()) > JOURNAL_TOKEN_CAP

    def compress(self, tier_config, game_state):
        full_text = self.read()
        system = build_system_prompt(self.agent_name, game_state)
        prompt = (
            f"Your journal is too long. Compress it to under {JOURNAL_COMPRESSION_TARGET} words. "
            f"Keep all key events and details.\n\n{full_text}"
        )
        compressed = call_personality(system, prompt, MAX_TOKENS["journal_compression"], tier_config)
        self._entries = [compressed.strip()]
        self._save()
        return compressed

    def entry_count(self):
        return len(self._entries)

    def token_count(self):
        return _token_count(self.read())


class Agent:
    def __init__(self, name):
        self.name = name
        self.journal = Journal(name)
        self.mailbox = Mailbox(name)

    def system_prompt(self, game_state):
        return build_system_prompt(self.name, game_state)

    def collect_morning_letters(self):
        return self.mailbox.collect_and_clear()


def load_alive_agents(game_state):
    return {name: Agent(name) for name in game_state["alive"]}


def load_game_state():
    path = os.path.join(DATA_DIR, "game_state.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_game_state(game_state):
    path = os.path.join(DATA_DIR, "game_state.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(game_state, f, indent=2)
