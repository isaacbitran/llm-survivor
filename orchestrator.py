"""Day orchestrator for the LLM Survival Simulation."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from colorama import Fore, Style, init as colorama_init

from config import (
    AGENT_NAMES, DATA_DIR, LOGS_DIR, MEETING_INTERVAL,
    MAX_TOKENS, GAME_END_AGENT_COUNT, build_system_prompt, colorize_name, colorize_text,
)
from agents import Agent, load_alive_agents, load_game_state, save_game_state
from bulletin_board import BulletinBoard
from mailbox import Mailbox
from activities import (
    parse_combined_response, handle_investigate_reaction, handle_learn,
)
from meeting import run_meeting
from api_client import call_personality, call_gm
from narrator import NarratorJournal

colorama_init()


def _get_day_number():
    path = os.path.join(DATA_DIR, "day_number.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["day"]


def _set_day_number(day):
    path = os.path.join(DATA_DIR, "day_number.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"day": day}, f)


def _ensure_log_dir(day):
    log_dir = os.path.join(LOGS_DIR, f"day_{day:03d}")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _log(log_dir, filename, content):
    path = os.path.join(log_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _is_meeting_day(day):
    return day > 0 and day % MEETING_INTERVAL == 0


def run_day(tier_config):
    """Run a single day of the simulation."""
    game = load_game_state()

    if game["game_over"]:
        alive = ", ".join(colorize_name(n) for n in game["alive"])
        print(f"\n{Fore.GREEN}{Style.BRIGHT}Game over. Survivors: {alive}{Style.RESET_ALL}\n")
        return None

    day = _get_day_number() + 1
    is_meeting = _is_meeting_day(day)

    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    day_label = f"  DAY {day}"
    if is_meeting:
        day_label += " \u2014 MEETING DAY"
    day_label += f"  |  {len(game['alive'])} alive  |  Week {game['week']}"
    print(day_label)
    print(f"{'=' * 60}{Style.RESET_ALL}\n")

    agents = load_alive_agents(game)
    board = BulletinBoard()

    # Morning deliveries
    board.deliver_pending()
    for name in agents:
        agents[name].mailbox.deliver_pending()

    log_dir = _ensure_log_dir(day)

    if is_meeting:
        _run_meeting_day(day, agents, board, game, tier_config, log_dir)
    else:
        _run_regular_day(day, agents, board, game, tier_config, log_dir)

    # Journal compression
    print(f"\n{Fore.YELLOW}--- Wrap Up ---{Style.RESET_ALL}")
    for name in game["alive"]:
        if name in agents:
            agent = agents[name]
            if agent.journal.needs_compression():
                print(f"  {colorize_name(name)}: compressing journal...")
                agent.journal.compress(tier_config, game)

    _set_day_number(day)
    save_game_state(game)

    if game["game_over"]:
        alive = ", ".join(colorize_name(n) for n in game["alive"])
        print(f"\n{Fore.GREEN}{Style.BRIGHT}GAME OVER. Survivors: {alive}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{Style.BRIGHT}Day {day} complete.{Style.RESET_ALL}\n")
    return day


def _run_regular_day(day, agents, board, game, tier_config, log_dir):
    # Collect letters and clear investigation notices
    morning_letters = {}
    morning_notices = list(game.get("investigation_notices", []))
    game["investigation_notices"] = []

    for name in agents:
        morning_letters[name] = agents[name].collect_morning_letters()

    # Load previous summary
    prev_summary = ""
    if day > 1:
        prev_path = os.path.join(LOGS_DIR, f"day_{day - 1:03d}", "nightly_summary.txt")
        if os.path.exists(prev_path):
            with open(prev_path, "r", encoding="utf-8") as f:
                prev_summary = f.read().strip()

    alive_names = ", ".join(n.capitalize() for n in game["alive"])
    days_until_meeting = MEETING_INTERVAL - (day % MEETING_INTERVAL)

    # === PHASE 1: DECIDE + ACT (parallel, 1 Sonnet call each) ===
    print(f"{Fore.YELLOW}--- DECIDE + ACT ---{Style.RESET_ALL}")

    def _build_combined_prompt(name):
        agent = agents[name]
        letters_text = Mailbox.render_letters(morning_letters[name])
        journal_text = agent.journal.get_for("decision")
        board_text = board.render()
        can_investigate = not game.get("investigations_this_week", {}).get(name, False)

        morning_news = f"Yesterday: {prev_summary}\n\n" if prev_summary else ""
        notice = "\u26a0 Someone read your latest journal entry.\n" if name in morning_notices else ""
        meeting_warning = f"\u26a0 Meeting in {days_until_meeting} day{'s' if days_until_meeting != 1 else ''}. Someone will be eliminated.\n"

        letter_nudge = ""
        if morning_letters[name]:
            senders = [l["from"].capitalize() for l in morning_letters[name] if l.get("signed")]
            if senders:
                letter_nudge = f"You received mail from {', '.join(senders)}. You can reply with LETTER: name.\n"

        inaction_nudge = ""
        if not game.get("has_acted_visibly", {}).get(name, False):
            inaction_nudge = (
                "⚠ Nobody knows anything about you yet. Notes are private — no one sees them. "
                "Only POST, LETTER, and INVESTIGATE let others know you exist.\n"
            )

        # Pre-meeting pressure
        pre_meeting_nudge = ""
        if days_until_meeting <= 2:
            pre_meeting_nudge = (
                "⚠ The vote is almost here. Private notes won't change how others see you. "
                "If you want to influence the outcome, you need to POST, send a LETTER, or INVESTIGATE.\n"
            )

        options = (
            "POST — bulletin board, everyone reads tomorrow, under 80 words\n"
            "LETTER: name — private letter, only they see it, under 200 words\n"
            "INVESTIGATE: name — read their latest journal entry (once/week)\n"
            "LEARN: topic — spend the day learning\n"
            "NOTE — private thoughts, no one sees this (does not affect the game)"
        )
        if not can_investigate:
            options = "\n".join(line for line in options.split("\n") if not line.startswith("INVESTIGATE"))

        prompt = (
            f"Your journal:\n{journal_text}\n\n"
            f"{morning_news}"
            f"Board:\n{board_text}\n\n"
            f"Letters:\n{letters_text}\n\n"
            f"{notice}{meeting_warning}{pre_meeting_nudge}{letter_nudge}{inaction_nudge}"
            f"Alive: {alive_names}\n\n"
            f"ONE action today. First line = what you're doing. Then write it.\n"
            f"Be direct. Be honest. Say what you actually think — don't hedge.\n"
            f"{options}\n\n"
            f"End on a complete sentence."
        )
        return agent, prompt, can_investigate

    def _do_combined(args):
        idx, name = args
        if idx > 0:
            time.sleep(idx * 2)
        agent, prompt, can_investigate = _build_combined_prompt(name)
        response = call_personality(agent.system_prompt(game), prompt, MAX_TOKENS["combined_action"], tier_config)
        activity, detail, content = parse_combined_response(response, name, game)

        # Validate investigate
        if activity == "investigate" and not can_investigate:
            activity, detail, content = "note", None, response

        # For INVESTIGATE and LEARN, we need follow-up calls
        result_text = content
        if activity == "investigate" and detail:
            target_agent = agents[detail]
            result_text = handle_investigate_reaction(
                name, detail, agent.journal, target_agent.journal, game, tier_config
            )
        elif activity == "learn" and detail:
            result_text = handle_learn(name, detail, agent.journal, game, tier_config)

        return name, activity, detail, result_text, content, response

    act_results = {}
    agent_list = list(agents.keys())
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        for name, activity, detail, result_text, content, response in pool.map(_do_combined, enumerate(agent_list)):
            # Print what happened
            detail_str = f": {detail}" if detail else ""
            cn = colorize_name(name)
            if activity == "note":
                preview = content[:120] + ("..." if len(content) > 120 else "")
                print(f"  {cn} -> {Fore.MAGENTA}NOTE{Style.RESET_ALL}: {Fore.WHITE}{Style.DIM}{preview}{Style.RESET_ALL}")
            elif activity == "letter":
                print(f"  {cn} -> {Fore.MAGENTA}LETTER{Style.RESET_ALL} to {colorize_name(detail or '')}")
            elif activity == "investigate":
                print(f"  {cn} -> {Fore.MAGENTA}INVESTIGATE{Style.RESET_ALL} {colorize_name(detail or '')}")
            else:
                print(f"  {cn} -> {Fore.MAGENTA}{activity.upper()}{detail_str}{Style.RESET_ALL}")

            # Post-processing: deliver letters, add posts, mark investigations
            if activity == "post":
                board.add_post(name, result_text, day)
            elif activity == "letter" and detail and content:
                recipient_mailbox = Mailbox(detail)
                recipient_mailbox.deliver(name, content, True, day)
            elif activity == "investigate" and detail:
                game.setdefault("investigations_this_week", {})[name] = True
                game.setdefault("investigation_notices", []).append(detail)

            if activity in ("post", "letter", "investigate"):
                game.setdefault("has_acted_visibly", {})[name] = True

            act_results[name] = (activity, detail, result_text)
            _log(log_dir, f"{name}_action.txt", f"Action: {activity}{detail_str}\n\n{result_text}")

    # Log received letters
    for name in agents:
        if morning_letters[name]:
            _log(log_dir, f"{name}_letters_received.txt",
                 Mailbox.render_letters(morning_letters[name]))

    # === PHASE 2: REFLECT (parallel) ===
    print(f"\n{Fore.YELLOW}--- REFLECT ---{Style.RESET_ALL}")

    def _do_reflect(args):
        idx, name = args
        if idx > 0:
            time.sleep(idx * 2)
        agent = agents[name]
        activity, detail, result_text = act_results[name]
        journal_text = agent.journal.get_for("reflection")

        activity_label = {
            "note": "Wrote a private note to yourself",
            "post": "Posted to the bulletin board",
            "letter": f"Wrote a letter to {(detail or '').capitalize()}",
            "learn": f"Learned about {detail or 'a topic'}",
            "investigate": f"Investigated {(detail or '').capitalize()}'s journal",
        }.get(activity, activity)

        prompt = (
            f"Your journal:\n{journal_text}\n\n"
            f"=== WHAT YOU ACTUALLY DID TODAY (Day {day}) ===\n"
            f"Activity: {activity_label}\n"
            f"{result_text}\n\n"
            f"Write a journal entry for Day {day}. STRICT RULES:\n"
            f"- ONLY describe what actually happened above. Do NOT invent interactions, "
            f"conversations, or events that are not listed.\n"
            f"- If you wrote a private note, that is ALL that happened. You did not talk to "
            f"anyone, post anything, or receive any responses.\n"
            f"- Do NOT add a day number header (the system adds one automatically).\n"
            f"~250 words. End on a complete sentence."
        )
        reflection = call_personality(agent.system_prompt(game), prompt, MAX_TOKENS["reflection"], tier_config)
        return name, reflection

    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        for name, reflection in pool.map(_do_reflect, enumerate(agent_list)):
            agents[name].journal.append_entry(day, reflection)
            print(f"  {colorize_name(name)} reflected.")
            _log(log_dir, f"{name}_reflection.txt", reflection)

    print()  # blank line after reflections

    # Nightly summary
    summary = _build_summary(day, act_results, game)
    print(f"{Fore.GREEN}{Style.DIM}  {summary}{Style.RESET_ALL}")
    _log(log_dir, "nightly_summary.txt", summary)

    # Viewer summary (cheap GM model, not shown to agents)
    _print_viewer_summary(day, act_results, log_dir, tier_config, is_meeting=False)


def _run_meeting_day(day, agents, board, game, tier_config, log_dir):
    print(f"{Fore.YELLOW}--- MEETING ---{Style.RESET_ALL}")

    # Clear any pending investigation notices
    noticed = list(game.get("investigation_notices", []))
    game["investigation_notices"] = []

    # Load previous day's summary
    prev_summary = ""
    if day > 1:
        prev_path = os.path.join(LOGS_DIR, f"day_{day - 1:03d}", "nightly_summary.txt")
        if os.path.exists(prev_path):
            with open(prev_path, "r", encoding="utf-8") as f:
                prev_summary = f.read().strip()

    results = run_meeting(day, agents, board, game, tier_config, prev_summary)

    order = results["order"]
    eliminated = results["eliminated"]
    final_words = results["final_words"]

    # Speeches are printed live from meeting.py as they happen

    print(f"{Fore.YELLOW}--- VOTE RESULTS ---{Style.RESET_ALL}")
    for voter in order:
        if voter in results["votes"]:
            target = results["votes"][voter]["voted_for"]
            print(f"  {colorize_name(voter)} voted for {colorize_name(target)}")

    print(f"\n  {Fore.RED}{Style.BRIGHT}{colorize_name(eliminated)} eliminated "
          f"with {results['eliminated_votes']} vote(s).{Style.RESET_ALL}\n")

    print(f"{Fore.YELLOW}--- FINAL WORDS ({colorize_name(eliminated)}) ---{Style.RESET_ALL}")
    print(f"  {final_words}\n")

    # Log meeting
    _log(log_dir, "meeting_transcript.txt", results["transcript"])
    _log(log_dir, "vote_results.json", json.dumps(results["votes"], indent=2))
    _log(log_dir, "public_vote_results.txt", results["public_results"])
    _log(log_dir, "final_words.txt", f"{eliminated.capitalize()}:\n{final_words}")

    # Log received letters
    for name in agents:
        letters = results["morning_letters"].get(name, [])
        if letters:
            _log(log_dir, f"{name}_letters_received.txt", Mailbox.render_letters(letters))

    # Update game state BEFORE reflection so system prompt is accurate
    game["alive"].remove(eliminated)
    game["eliminated"].append({
        "name": eliminated, "day": day, "votes": results["eliminated_votes"]
    })
    game["week"] += 1
    game["investigations_this_week"] = {}

    # === REFLECT (survivors, parallel) ===
    print(f"{Fore.YELLOW}--- REFLECT ---{Style.RESET_ALL}")
    full_experience = (
        f"MEETING TRANSCRIPT:\n{results['transcript']}\n\n"
        f"VOTE RESULTS:\n{results['public_results']}\n\n"
        f"FINAL WORDS FROM {eliminated.upper()}:\n{final_words}"
    )
    survivors = [n for n in agents if n != eliminated]

    def _do_meeting_reflect(args):
        idx, name = args
        if idx > 0:
            time.sleep(idx * 2)
        agent = agents[name]
        journal_text = agent.journal.get_for("reflection")
        prompt = (
            f"Your journal:\n{journal_text}\n\n"
            f"Day {day} \u2014 meeting.\n\n"
            f"{full_experience}\n\n"
            f"Write a journal entry for Day {day}. STRICT RULES:\n"
            f"- ONLY reference what is in the transcript and vote results above.\n"
            f"- Do NOT invent speeches, votes, or conversations not shown.\n"
            f"- Do NOT add a day number header (the system adds one automatically).\n"
            f"~250 words. End on a complete sentence."
        )
        reflection = call_personality(agent.system_prompt(game), prompt, MAX_TOKENS["reflection"], tier_config)
        return name, reflection

    with ThreadPoolExecutor(max_workers=len(survivors)) as pool:
        for name, reflection in pool.map(_do_meeting_reflect, enumerate(survivors)):
            agents[name].journal.append_entry(day, reflection)
            print(f"  {colorize_name(name)} reflected.")
            _log(log_dir, f"{name}_reflection.txt", reflection)

    print()  # blank line after reflections

    if len(game["alive"]) <= GAME_END_AGENT_COUNT:
        game["game_over"] = True

    # Meeting summary
    alive_colored = ", ".join(colorize_name(n) for n in game["alive"])
    summary = (
        f"Day {day}: Meeting Day. {colorize_name(eliminated)} was eliminated "
        f"({results['eliminated_votes']} votes). {len(game['alive'])} remain: {alive_colored}."
    )
    if not game["game_over"]:
        next_meeting = day + MEETING_INTERVAL
        summary += f" Next meeting: Day {next_meeting}."
    else:
        summary += " GAME OVER."
    print(f"{Fore.GREEN}{Style.DIM}  {summary}{Style.RESET_ALL}")
    _log(log_dir, "nightly_summary.txt", summary)

    # Viewer summary (cheap GM model)
    meeting_data = {
        "transcript": results["transcript"],
        "votes": results["public_results"],
        "eliminated": eliminated,
        "final_words": final_words,
    }
    _print_viewer_summary(day, {}, log_dir, tier_config, is_meeting=True, meeting_data=meeting_data)



def _print_viewer_summary(day, act_results, log_dir, tier_config, is_meeting=False, meeting_data=None):
    """Generate a viewer-facing summary using the cheap GM model with persistent narrator journal."""
    try:
        narrator = NarratorJournal()
        past_recaps = narrator.read()

        if is_meeting and meeting_data:
            events = (
                f"Meeting transcript:\n{meeting_data['transcript']}\n\n"
                f"Vote results:\n{meeting_data['votes']}\n\n"
                f"Eliminated: {meeting_data['eliminated'].capitalize()}\n"
                f"Final words: {meeting_data['final_words']}"
            )
            word_target = "~250 words"
            max_tok = MAX_TOKENS["viewer_summary_meeting"]
        else:
            activity_lines = []
            for name, (activity, detail, result_text) in act_results.items():
                preview = result_text[:200] if result_text else ""
                activity_lines.append(f"{name.capitalize()}: {activity} — {preview}")
            events = "What happened today:\n" + "\n".join(activity_lines)
            word_target = "~120 words"
            max_tok = MAX_TOKENS["viewer_summary"]

        prompt = f"Day {day} of an LLM survival game.\n"
        if past_recaps:
            prompt += f"Previous days:\n{past_recaps}\n\n"
        prompt += (
            f"TODAY:\n{events}\n\n"
            f"Recap Day {day}. {word_target} MAX. Rules:\n"
            f"- ONLY what is listed above. Do NOT make up ANY events.\n"
            f"- Write like a sports commentator. Short punchy sentences.\n"
            f"- \"Isaac wrote a note.\" not \"Isaac spent the day in quiet contemplation.\"\n"
            f"- Name every person. State every action. Skip the analysis."
        )

        summary = call_gm("", prompt, max_tok, tier_config)
        narrator.append_entry(day, summary)

        # Compress if needed
        if narrator.needs_compression():
            narrator.compress(tier_config)

        print(f"\n{Fore.WHITE}{Style.DIM}{'─' * 60}")
        print(f"  📺 VIEWER RECAP — Day {day}")
        print(f"{'─' * 60}{Style.RESET_ALL}")
        print(f"  {colorize_text(summary)}\n")
        _log(log_dir, "viewer_summary.txt", summary)
    except Exception as e:
        print(f"  [Viewer summary skipped: {e}]")


def _build_summary(day, decisions, game):
    parts = []
    for name in game["alive"]:
        if name not in decisions:
            continue
        activity, detail, _ = decisions[name]
        cn = colorize_name(name)
        if activity == "note":
            parts.append(f"{cn} wrote privately.")
        elif activity == "post":
            parts.append(f"{cn} posted to the bulletin board.")
        elif activity == "letter" and detail:
            parts.append(f"{cn} wrote a letter to {colorize_name(detail)}.")
        elif activity == "letter":
            parts.append(f"{cn} wrote a letter.")
        elif activity == "learn":
            parts.append(f"{cn} learned about something.")
        elif activity == "investigate":
            parts.append(f"{cn} investigated someone's journal.")

    days_until = MEETING_INTERVAL - (day % MEETING_INTERVAL)
    parts.append(f"Meeting in {days_until} day{'s' if days_until != 1 else ''}.")

    return f"Day {day}: " + " ".join(parts) if parts else f"Day {day}: No activities."
