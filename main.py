"""Main entry point for the LLM Survival Simulation."""

import argparse
import io
import json
import os
import shutil
import sys

# Force UTF-8 stdout on Windows to handle emoji/unicode
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from config import (
    AGENT_NAMES, DATA_DIR, LOGS_DIR, TIERS, DEFAULT_TIER,
    MEETING_INTERVAL, colorize_name, colorize_text,
)
from api_client import validate_api_keys


def init_data():
    """Initialize (or reinitialize) all data and logs."""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(LOGS_DIR):
        shutil.rmtree(LOGS_DIR)
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Game state
    game_state = {
        "week": 1,
        "alive": list(AGENT_NAMES),
        "eliminated": [],
        "investigations_this_week": {},
        "investigation_notices": [],
        "has_acted_visibly": {},  # tracks if agent has ever posted/lettered/investigated
        "game_over": False,
    }
    with open(os.path.join(DATA_DIR, "game_state.json"), "w", encoding="utf-8") as f:
        json.dump(game_state, f, indent=2)

    # Day counter
    with open(os.path.join(DATA_DIR, "day_number.json"), "w", encoding="utf-8") as f:
        json.dump({"day": 0}, f)

    # Bulletin board with seed post
    seed_post = {
        "author": "unknown",
        "day": 0,
        "content": (
            "To whoever finds this: there are 7 of you here. "
            "You have this board, you can write letters, "
            "and every 7 days you meet to vote. Good luck."
        ),
    }
    with open(os.path.join(DATA_DIR, "bulletin_board.json"), "w", encoding="utf-8") as f:
        json.dump({"posts": [seed_post], "pending": []}, f, indent=2)

    # Clear narrator journal
    narrator_path = os.path.join(DATA_DIR, "narrator_journal.txt")
    if os.path.exists(narrator_path):
        os.remove(narrator_path)

    # Agent directories
    for name in AGENT_NAMES:
        agent_dir = os.path.join(DATA_DIR, "agents", name)
        os.makedirs(agent_dir, exist_ok=True)
        with open(os.path.join(agent_dir, "journal.txt"), "w", encoding="utf-8") as f:
            f.write("")
        with open(os.path.join(agent_dir, "mailbox.json"), "w", encoding="utf-8") as f:
            json.dump({"letters": [], "pending": []}, f, indent=2)

    print("Data initialized. 7 agents. Let the game begin.")


def is_initialized():
    return (
        os.path.exists(os.path.join(DATA_DIR, "day_number.json"))
        and os.path.exists(os.path.join(DATA_DIR, "game_state.json"))
        and os.path.exists(os.path.join(DATA_DIR, "bulletin_board.json"))
    )


def show_status():
    if not is_initialized():
        print("Not initialized. Run with --reset.")
        return

    with open(os.path.join(DATA_DIR, "day_number.json"), "r", encoding="utf-8") as f:
        day = json.load(f)["day"]

    with open(os.path.join(DATA_DIR, "game_state.json"), "r", encoding="utf-8") as f:
        game = json.load(f)

    print(f"\n=== LLM Survival Simulation ===")
    print(f"Day: {day}  |  Week: {game['week']}  |  Alive: {len(game['alive'])}")

    if game["game_over"]:
        survivors = ", ".join(colorize_name(n) for n in game["alive"])
        print(f"GAME OVER. Survivors: {survivors}")
    else:
        if day == 0:
            days_until = MEETING_INTERVAL
        else:
            days_until = MEETING_INTERVAL - (day % MEETING_INTERVAL)
            if days_until == 0:
                days_until = MEETING_INTERVAL
        print(f"Next meeting: Day {day + days_until}")

    print(f"\n--- Alive ---")
    for name in game["alive"]:
        journal_path = os.path.join(DATA_DIR, "agents", name, "journal.txt")
        tokens = 0
        if os.path.exists(journal_path):
            with open(journal_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            tokens = len(content.split()) if content else 0
        print(f"  {colorize_name(name)}: {tokens} tokens")

    if game["eliminated"]:
        print(f"\n--- Eliminated ---")
        for entry in game["eliminated"]:
            print(f"  {colorize_name(entry['name'])}: Day {entry['day']} ({entry['votes']} votes)")

    print(f"\n--- Board ---")
    with open(os.path.join(DATA_DIR, "bulletin_board.json"), "r", encoding="utf-8") as f:
        board_data = json.load(f)
    posts = board_data.get("posts", [])
    print(f"  {len(posts)} post(s)")
    for post in posts[-3:]:
        preview = post["content"][:80] + "..." if len(post["content"]) > 80 else post["content"]
        print(f"    {colorize_name(post['author'])} (day {post['day']}): {preview}")
    print()


def run_summary(agent_name, tier_config):
    """Generate a GM-model summary of a specific agent's full story so far."""
    from api_client import call_gm

    agent_name = agent_name.lower()
    if agent_name not in AGENT_NAMES:
        print(f"Unknown agent: {agent_name}. Choose from: {', '.join(colorize_name(n) for n in AGENT_NAMES)}")
        return

    # Read their journal
    journal_path = os.path.join(DATA_DIR, "agents", agent_name, "journal.txt")
    if not os.path.exists(journal_path):
        print(f"{colorize_name(agent_name)} has no journal yet.")
        return
    with open(journal_path, "r", encoding="utf-8") as f:
        journal = f.read().strip()
    if not journal:
        print(f"{agent_name.capitalize()}'s journal is empty.")
        return

    # Read game state for context
    with open(os.path.join(DATA_DIR, "game_state.json"), "r", encoding="utf-8") as f:
        game = json.load(f)

    is_alive = agent_name in game["alive"]
    elim_info = ""
    for e in game["eliminated"]:
        if e["name"] == agent_name:
            elim_info = f"\n{agent_name.capitalize()} was eliminated on Day {e['day']} with {e['votes']} votes."

    # Gather their activity logs
    activity_log = []
    if os.path.exists(LOGS_DIR):
        for entry in sorted(os.listdir(LOGS_DIR)):
            day_dir = os.path.join(LOGS_DIR, entry)
            activity_path = os.path.join(day_dir, f"{agent_name}_activity.txt")
            if os.path.exists(activity_path):
                with open(activity_path, "r", encoding="utf-8") as f:
                    activity_log.append(f"{entry}: {f.read().strip()[:200]}")

    activities_text = "\n".join(activity_log[-10:]) if activity_log else "No activities logged."

    prompt = (
        f"Summarize {agent_name.capitalize()} in an LLM survival game.\n\n"
        f"Status: {'ALIVE' if is_alive else 'ELIMINATED'}{elim_info}\n\n"
        f"Journal:\n{journal}\n\n"
        f"Activities:\n{activities_text}\n\n"
        f"Write a SHORT, factual summary. ~150 words MAX. No fluff, no metaphors, no philosophy.\n"
        f"State ONLY: what they did each week, who they wrote to, who they voted for, "
        f"who voted for them, current alliances, and whether they're safe or at risk.\n"
        f"Use plain language. Be blunt."
    )

    from colorama import Fore, Style, init as colorama_init
    colorama_init()

    print(f"\n{Fore.WHITE}{Style.DIM}{'=' * 60}")
    print(f"  \U0001f4fa PLAYER SUMMARY \u2014 {colorize_name(agent_name)}")
    print(f"{Fore.WHITE}{Style.DIM}{'=' * 60}{Style.RESET_ALL}\n")

    summary = call_gm("", prompt, 500, tier_config)
    print(f"  {colorize_text(summary)}\n")


def show_board():
    """Print the full bulletin board."""
    board_path = os.path.join(DATA_DIR, "bulletin_board.json")
    if not os.path.exists(board_path):
        print("No board data. Run --reset first.")
        return
    with open(board_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    posts = data.get("posts", [])
    pending = data.get("pending", [])
    print(f"\n{'=' * 60}")
    print(f"  BULLETIN BOARD  ({len(posts)} post{'s' if len(posts) != 1 else ''})")
    print(f"{'=' * 60}\n")
    if not posts:
        print("  [empty]")
    for post in posts:
        author = colorize_name(post["author"])
        print(f"  {author} (day {post['day']}):")
        print(f"    {post['content']}\n")
    if pending:
        print(f"  --- {len(pending)} pending (visible tomorrow) ---")
        for post in pending:
            print(f"    {colorize_name(post['author'])} (day {post['day']})")
    print()


def main():
    parser = argparse.ArgumentParser(description="LLM Survival Simulation")
    parser.add_argument("--mode", choices=["day", "days", "status", "summary", "board"], default="day")
    parser.add_argument("--tier", choices=list(TIERS.keys()), default=DEFAULT_TIER)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--player", type=str, help="Agent name for --mode summary")
    args = parser.parse_args()

    tier_config = TIERS[args.tier]

    if args.reset:
        print(f"Tier: {tier_config['name']}")
        init_data()
        if args.mode == "status":
            show_status()
        return

    if not is_initialized():
        print("Not initialized. Initializing...")
        init_data()

    if args.mode == "status":
        show_status()
        return

    if args.mode == "board":
        show_board()
        return

    if args.mode == "summary":
        if not args.player:
            print("Usage: python main.py --mode summary --player <name>")
            print(f"Agents: {', '.join(n.capitalize() for n in AGENT_NAMES)}")
            return
        errors = validate_api_keys(tier_config)
        if errors:
            for e in errors:
                print(f"ERROR: {e}")
            sys.exit(1)
        run_summary(args.player, tier_config)
        return

    print(f"Tier: {tier_config['name']}")

    errors = validate_api_keys(tier_config)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)

    from orchestrator import run_day

    try:
        if args.mode == "day":
            run_day(tier_config)
        elif args.mode == "days":
            for i in range(args.count):
                print(f"\n{'#' * 60}")
                print(f"  Running day {i + 1} of {args.count}")
                print(f"{'#' * 60}")
                result = run_day(tier_config)
                if result is None:  # Game over
                    break
    except Exception as e:
        err = str(e).lower()
        if "credit balance" in err or "invalid_api_key" in err or "authentication" in err:
            print(f"\n❌ API billing/auth error. Check your credits at console.anthropic.com")
        else:
            print(f"\n❌ {e}")
        print("Day did not complete. No state was saved. Safe to retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
