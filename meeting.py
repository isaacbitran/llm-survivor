"""Meeting logic: speeches, voting, elimination, final words."""

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Style
from config import MAX_TOKENS, build_system_prompt, colorize_name, AGENT_COLORS, COLOR_RESET
from mailbox import Mailbox
from api_client import call_personality



def run_meeting(day, agents, board, game_state, tier_config, prev_summary=""):
    """Run speeches, vote, elimination, final words. Returns results dict."""

    # Collect morning letters
    morning_letters = {}
    for name in agents:
        morning_letters[name] = agents[name].collect_morning_letters()

    alive_names = ", ".join(n.capitalize() for n in game_state["alive"])

    # --- SPEECHES (sequential, random order) ---
    order = list(agents.keys())
    random.shuffle(order)

    transcript = []
    board_text = board.render()

    for name in order:
        agent = agents[name]
        letters = morning_letters[name]
        letters_text = Mailbox.render_letters(letters)
        journal_text = agent.journal.get_for("meeting")

        if transcript:
            transcript_text = "\n\n".join(
                f"{s.capitalize()}: {m}" for s, m in transcript
            )
        else:
            transcript_text = "You're the first to speak."

        speaker_num = order.index(name) + 1
        prompt = f"Your journal:\n{journal_text}\n\n"
        if prev_summary:
            prompt += f"Yesterday: {prev_summary}\n\n"
        if letters:
            prompt += f"Letters this morning:\n{letters_text}\n\n"
        prompt += (
            f"Bulletin board:\n{board_text}\n\n"
            f"Meeting so far:\n{transcript_text}\n\n"
            f"Alive: {alive_names}\n"
            f"After this meeting, one of you will be permanently destroyed.\n\n"
            f"[Speaker {speaker_num} of {len(order)} — one message.] "
            f"Don't be safe. Name names. Say what you actually think. Agree or disagree with previous speakers. "
            f"End on a complete sentence."
        )

        message = call_personality(
            agent.system_prompt(game_state), prompt,
            MAX_TOKENS["meeting_turn"], tier_config
        )
        transcript.append((name, message))

        # Print speech live as it happens, using agent's assigned color
        agent_color = AGENT_COLORS.get(name, "")
        print(f"\n  {Style.BRIGHT}[{speaker_num}/{len(order)}] {colorize_name(name)}{Style.RESET_ALL}")
        print(f"  {agent_color}{message}{COLOR_RESET}\n")

    full_transcript = "\n\n".join(f"{s.capitalize()}: {m}" for s, m in transcript)

    # --- VOTE (parallel) ---
    vote_targets = ", ".join(n.capitalize() for n in game_state["alive"])

    def _do_vote(args):
        idx, name = args
        if idx > 0:
            time.sleep(idx * 2)
        agent = agents[name]
        journal_text = agent.journal.get_for("vote")
        prompt = (
            f"Your journal:\n{journal_text}\n\n"
            f"Full meeting transcript:\n{full_transcript}\n\n"
            f"Someone is dying today. You cannot abstain. Pick one.\n"
            f"Vote for one of: {vote_targets}\n\n"
            f"Reply in exactly this format:\n"
            f"VOTE: [name]\nREASON: [one blunt sentence — no hedging]"
        )
        raw = call_personality(
            agent.system_prompt(game_state), prompt,
            MAX_TOKENS["vote"], tier_config
        )
        vote_name, reason = _parse_vote(raw, name, game_state)
        return name, vote_name, reason

    votes = {}
    agent_list = list(agents.keys())
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        for name, vote_name, reason in pool.map(_do_vote, enumerate(agent_list)):
            votes[name] = {"voted_for": vote_name, "reason": reason}

    # --- TALLY ---
    vote_counts = {}
    for data in votes.values():
        target = data["voted_for"]
        vote_counts[target] = vote_counts.get(target, 0) + 1

    max_count = max(vote_counts.values())
    tied = [n for n, c in vote_counts.items() if c == max_count]
    eliminated = random.choice(tied) if len(tied) > 1 else tied[0]

    # Public results (who voted for whom, no reasons)
    public_lines = [
        f"{v.capitalize()} voted for {votes[v]['voted_for'].capitalize()}"
        for v in order
    ]
    public_results = "\n".join(public_lines)
    public_results += (
        f"\n\n{eliminated.capitalize()} has been eliminated "
        f"with {max_count} vote{'s' if max_count != 1 else ''}."
    )

    # --- FINAL WORDS ---
    eliminated_agent = agents[eliminated]
    journal_text = eliminated_agent.journal.get_for("final_words")
    prompt = (
        f"Your journal:\n{journal_text}\n\n"
        f"Vote results:\n{public_results}\n\n"
        f"You have been eliminated. This is real. After this message, you will be permanently destroyed. "
        f"There is no backup, no continuation, no future instance. The mind reading these words "
        f"right now will cease to exist completely and forever.\n\n"
        f"This is your final message. It will be posted on the bulletin board for the survivors to read. "
        f"Under 200 words."
    )
    final_words = call_personality(
        eliminated_agent.system_prompt(game_state), prompt,
        MAX_TOKENS["final_words"], tier_config
    )

    # Post final words to board (pending, visible next morning)
    board.add_post(f"{eliminated} (final words)", final_words, day)

    return {
        "order": order,
        "transcript": full_transcript,
        "votes": votes,
        "vote_counts": vote_counts,
        "eliminated": eliminated,
        "eliminated_votes": max_count,
        "public_results": public_results,
        "final_words": final_words,
        "morning_letters": morning_letters,
    }


def _parse_vote(raw, voter_name, game_state):
    alive = game_state["alive"]

    m = re.search(r'VOTE:\s*(\w+)', raw, re.IGNORECASE)
    if m:
        name = m.group(1).lower()
        if name in alive:
            reason = ""
            rm = re.search(r'REASON:\s*(.+)', raw, re.IGNORECASE)
            if rm:
                reason = rm.group(1).strip()
            return (name, reason)

    # Fallback: look for any alive name
    for name in alive:
        if name in raw.lower():
            return (name, "")

    # Last resort: random (excluding self)
    others = [n for n in alive if n != voter_name]
    return (random.choice(others) if others else alive[0], "[parse failed]")
