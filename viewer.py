"""Web viewer for the LLM Life Simulation — serves on localhost:8000."""

import json
import os
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from config import AGENT_NAMES, DATA_DIR, LOGS_DIR


class SimulationAPI:
    """Reads simulation data for API responses."""

    @staticmethod
    def get_day_number():
        path = os.path.join(DATA_DIR, "day_number.json")
        if not os.path.exists(path):
            return 0
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)["day"]

    @staticmethod
    def get_status():
        day = SimulationAPI.get_day_number()
        agents = []
        for name in AGENT_NAMES:
            journal_path = os.path.join(DATA_DIR, "agents", name, "journal.txt")
            content = ""
            if os.path.exists(journal_path):
                with open(journal_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            agents.append({
                "name": name,
                "journal_tokens": len(content.split()) if content else 0,
            })
        return {"day": day, "agents": agents}

    @staticmethod
    def get_board():
        path = os.path.join(DATA_DIR, "bulletin_board.json")
        if not os.path.exists(path):
            return {"posts": []}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"posts": data.get("posts", [])}

    @staticmethod
    def get_days():
        days = []
        if not os.path.exists(LOGS_DIR):
            return days
        for entry in sorted(os.listdir(LOGS_DIR)):
            m = re.match(r"day_(\d+)", entry)
            if m:
                day_num = int(m.group(1))
                day_dir = os.path.join(LOGS_DIR, entry)
                summary_path = os.path.join(day_dir, "nightly_summary.txt")
                summary = ""
                if os.path.exists(summary_path):
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary = f.read().strip()
                is_meeting = os.path.exists(os.path.join(day_dir, "meeting_transcript.txt"))
                days.append({
                    "day": day_num,
                    "summary": summary,
                    "is_meeting": is_meeting,
                })
        return days

    @staticmethod
    def get_day(day_num):
        day_dir = os.path.join(LOGS_DIR, f"day_{day_num:03d}")
        if not os.path.exists(day_dir):
            return None
        result = {"day": day_num, "agents": {}, "is_meeting": False}

        # Check for meeting transcript
        meeting_path = os.path.join(day_dir, "meeting_transcript.txt")
        if os.path.exists(meeting_path):
            result["is_meeting"] = True
            with open(meeting_path, "r", encoding="utf-8") as f:
                result["meeting_transcript"] = f.read()

        # Summary
        summary_path = os.path.join(day_dir, "nightly_summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                result["summary"] = f.read().strip()

        # Per-agent logs
        for name in AGENT_NAMES:
            agent_data = {}
            for suffix in ["action", "reflection", "letters_received"]:
                fpath = os.path.join(day_dir, f"{name}_{suffix}.txt")
                if os.path.exists(fpath):
                    with open(fpath, "r", encoding="utf-8") as f:
                        agent_data[suffix] = f.read()
            if agent_data:
                result["agents"][name] = agent_data

        return result

    @staticmethod
    def get_agents():
        agents = []
        for name in AGENT_NAMES:
            journal_path = os.path.join(DATA_DIR, "agents", name, "journal.txt")
            content = ""
            if os.path.exists(journal_path):
                with open(journal_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            agents.append({
                "name": name,
                "journal": content,
                "journal_tokens": len(content.split()) if content else 0,
            })
        return agents

    @staticmethod
    def get_agent(name):
        if name not in AGENT_NAMES:
            return None
        journal_path = os.path.join(DATA_DIR, "agents", name, "journal.txt")
        content = ""
        if os.path.exists(journal_path):
            with open(journal_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

        # Gather activity history from logs
        history = []
        if os.path.exists(LOGS_DIR):
            for entry in sorted(os.listdir(LOGS_DIR)):
                m = re.match(r"day_(\d+)", entry)
                if m:
                    day_num = int(m.group(1))
                    day_dir = os.path.join(LOGS_DIR, entry)
                    day_data = {"day": day_num}
                    for suffix in ["action", "reflection", "letters_received"]:
                        fpath = os.path.join(day_dir, f"{name}_{suffix}.txt")
                        if os.path.exists(fpath):
                            with open(fpath, "r", encoding="utf-8") as f:
                                day_data[suffix] = f.read()
                    if len(day_data) > 1:
                        history.append(day_data)

        return {
            "name": name,
            "journal": content,
            "journal_tokens": len(content.split()) if content else 0,
            "history": history,
        }


class ViewerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the simulation viewer."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # API routes
        if path == "/api/status":
            self._json_response(SimulationAPI.get_status())
        elif path == "/api/board":
            self._json_response(SimulationAPI.get_board())
        elif path == "/api/days":
            self._json_response(SimulationAPI.get_days())
        elif path == "/api/agents":
            self._json_response(SimulationAPI.get_agents())
        elif path.startswith("/api/day/"):
            try:
                day_num = int(path.split("/")[-1])
                data = SimulationAPI.get_day(day_num)
                if data:
                    self._json_response(data)
                else:
                    self._json_response({"error": "Day not found"}, 404)
            except ValueError:
                self._json_response({"error": "Invalid day number"}, 400)
        elif path.startswith("/api/agent/"):
            name = path.split("/")[-1].lower()
            data = SimulationAPI.get_agent(name)
            if data:
                self._json_response(data)
            else:
                self._json_response({"error": "Agent not found"}, 404)

        # Static files
        elif path == "/static/style.css":
            self._serve_static("static/style.css", "text/css")

        # HTML pages
        elif path == "/":
            self._serve_template("index.html")
        elif path == "/board":
            self._serve_template("board.html")
        elif path == "/analytics":
            self._serve_template("analytics.html")
        elif path.startswith("/day/"):
            self._serve_template("day.html")
        elif path.startswith("/agent/"):
            self._serve_template("agent.html")
        else:
            self._text_response("Not found", 404)

    def _json_response(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_template(self, filename):
        filepath = os.path.join("templates", filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            body = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._text_response(f"Template not found: {filename}", 404)

    def _serve_static(self, filepath, content_type):
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            body = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._text_response("Not found", 404)

    def _text_response(self, text, status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_viewer(port=8000):
    server = HTTPServer(("localhost", port), ViewerHandler)
    print(f"Viewer running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nViewer stopped.")
        server.server_close()


if __name__ == "__main__":
    run_viewer()
