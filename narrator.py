"""Narrator journal — cheap GM model recap for viewers, with persistent memory."""

import os
import re
from config import (
    DATA_DIR, JOURNAL_TOKEN_CAP, JOURNAL_COMPRESSION_TARGET, MAX_TOKENS,
)
from api_client import call_gm


def _token_count(text):
    return len(text.split())


class NarratorJournal:
    """Persistent journal for the viewer narrator. Same structure as agent journals."""

    def __init__(self):
        self.filepath = os.path.join(DATA_DIR, "narrator_journal.txt")
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

    def append_entry(self, day, text):
        words = text.split()
        if len(words) > 350:
            words = words[:350]
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

    def compress(self, tier_config):
        full_text = self.read()
        prompt = (
            f"Compress this game recap journal to under {JOURNAL_COMPRESSION_TARGET} words. "
            f"Be factual and straightforward. Keep: who was eliminated and why, "
            f"who is allied with whom, key letters/posts, vote results. Cut fluff.\n\n"
            f"Journal:\n{full_text}"
        )
        compressed = call_gm("", prompt, MAX_TOKENS["journal_compression"], tier_config)
        self._entries = [compressed.strip()]
        self._save()
