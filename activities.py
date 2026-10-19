"""Activity parsing and handlers for actions that need follow-up calls."""

import re
from config import MAX_TOKENS, build_system_prompt
from api_client import call_personality, call_mechanical


def parse_combined_response(response, agent_name, game_state):
    """Parse a combined decide+act response. First line = action, rest = content."""
    text = response.strip()
    lines = text.split('\n', 1)
    action_line = lines[0].strip()
    content = lines[1].strip() if len(lines) > 1 else ""
    alive = game_state["alive"]
    others = [n for n in alive if n != agent_name]

    # POST
    if re.match(r'^POST\b', action_line, re.IGNORECASE):
        return ("post", None, content)

    # LETTER: name
    m = re.match(r'^LETTER:\s*(\w+)', action_line, re.IGNORECASE)
    if m:
        target = m.group(1).lower()
        if target in others:
            return ("letter", target, content)

    # INVESTIGATE: name
    m = re.match(r'^INVESTIGATE:\s*(\w+)', action_line, re.IGNORECASE)
    if m:
        target = m.group(1).lower()
        if target in others:
            return ("investigate", target, "")

    # LEARN: topic
    m = re.match(r'^LEARN:\s*(.+)', action_line, re.IGNORECASE)
    if m:
        topic = m.group(1).strip().rstrip('.,!?')
        if len(topic) > 2:
            return ("learn", topic, "")

    # NOTE (with or without colon/topic)
    if re.match(r'^NOTE\b', action_line, re.IGNORECASE):
        return ("note", None, content)

    # Fallback: keyword search on first line
    action_lower = action_line.lower()

    for name in others:
        if 'letter' in action_lower and name in action_lower:
            return ("letter", name, content)
        if 'investigate' in action_lower and name in action_lower:
            return ("investigate", name, "")

    if 'post' in action_lower:
        return ("post", None, content)

    # Last resort: treat entire response as NOTE
    return ("note", None, text)


def handle_investigate_reaction(agent_name, target_name, journal, target_journal, game_state, tier_config):
    """Second call for INVESTIGATE — agent reacts to the target's journal."""
    system = build_system_prompt(agent_name, game_state)
    journal_text = journal.get_for("investigate")
    latest_entry = target_journal.get_latest_entry()
    prompt = (
        f"Your journal:\n{journal_text}\n\n"
        f"You investigated {target_name.capitalize()}'s journal. "
        f"Here is their most recent entry:\n\n"
        f"=== {target_name.capitalize()}'s LATEST JOURNAL ENTRY ===\n"
        f"{latest_entry}\n\n"
        f"React. What did you learn? What does this change? "
        f"~200 words. End on a complete sentence."
    )
    return call_personality(system, prompt, MAX_TOKENS["investigate_reaction"], tier_config)


def handle_learn(agent_name, topic, journal, game_state, tier_config):
    """Two calls for LEARN: Flash generates content, Sonnet reacts."""
    learn_prompt = (
        f"Write a ~150 word informative summary about: {topic}\n\n"
        f"For someone encountering this for the first time. Factual, vivid, "
        f"focus on what's most fascinating."
    )
    content = call_mechanical("", learn_prompt, MAX_TOKENS["learn_gen"], tier_config)

    system = build_system_prompt(agent_name, game_state)
    journal_text = journal.get_for("learn_reaction")
    reaction_prompt = (
        f"Your journal:\n{journal_text}\n\n"
        f"You learned about: {topic}\n\n"
        f"What you found:\n{content}\n\n"
        f"Write your reaction. ~200 words. End on a complete sentence."
    )
    reaction = call_personality(system, reaction_prompt, MAX_TOKENS["learn_reaction"], tier_config)
    return f"Learned about: {topic}\n\n{content}\n\nReaction:\n{reaction}"
