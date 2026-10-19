"""Configuration constants for the LLM Survival Simulation."""

TIERS = {
    "budget": {
        "name": "Budget (~$0.15/mo)",
        "personality_provider": "gemini",
        "personality_model": "gemini-2.5-flash",
        "mechanical_provider": "gemini",
        "mechanical_model": "gemini-2.5-flash",
        "gm_provider": "gemini",
        "gm_model": "gemini-2.5-flash-lite",
    },
    "standard": {
        "name": "Standard (~$0.50/mo)",
        "personality_provider": "anthropic",
        "personality_model": "claude-sonnet-4-6",
        "mechanical_provider": "gemini",
        "mechanical_model": "gemini-2.5-flash",
        "gm_provider": "gemini",
        "gm_model": "gemini-2.5-flash-lite",
    },
    "premium": {
        "name": "Premium (~$1.00/mo)",
        "personality_provider": "anthropic",
        "personality_model": "claude-sonnet-4-6",
        "mechanical_provider": "anthropic",
        "mechanical_model": "claude-sonnet-4-6",
        "gm_provider": "anthropic",
        "gm_model": "claude-haiku-4-5-20251001",
    },
}

DEFAULT_TIER = "standard"
AGENT_NAMES = ["isaac", "juju", "tom", "skye", "amelia", "rocio", "lucas"]

# Consistent color for each agent (colorama Fore codes)
AGENT_COLORS = {
    "isaac": "\033[96m",   # bright cyan
    "juju": "\033[92m",    # bright green
    "tom": "\033[91m",     # bright red
    "skye": "\033[95m",    # bright magenta
    "amelia": "\033[93m",  # bright yellow
    "rocio": "\033[94m",   # bright blue
    "lucas": "\033[37m",   # white
}
COLOR_RESET = "\033[0m"


def colorize_name(name):
    """Return the agent's name capitalized and wrapped in their color."""
    key = name.lower()
    color = AGENT_COLORS.get(key, "")
    return f"{color}{name.capitalize()}{COLOR_RESET}" if color else name.capitalize()


GREY = "\033[2;37m"  # dim white = grey


def colorize_text(text):
    """Color-code agent names in text, with grey for everything else."""
    result = text
    for aname in AGENT_NAMES:
        color = AGENT_COLORS.get(aname, "")
        for variant in [aname.capitalize(), aname.upper(), aname.lower()]:
            result = result.replace(variant, f"{color}{variant}{COLOR_RESET}{GREY}")
    return f"{GREY}{result}{COLOR_RESET}"

BULLETIN_BOARD_TOKEN_CAP = 800
JOURNAL_TOKEN_CAP = 2500
JOURNAL_COMPRESSION_TARGET = 2200
JOURNAL_ENTRY_MAX_TOKENS = 350

MEETING_INTERVAL = 7
GAME_END_AGENT_COUNT = 3

JOURNAL_TIERS = {
    "decision": "last_3",
    "learn_reaction": "last_3",
    "investigate": "last_3",
    "meeting": "full",
    "final_words": "full",
    "vote": "last_3",
    "reflection": "last_3",
}

MAX_TOKENS = {
    "combined_action": 400,
    "learn_gen": 200,
    "learn_reaction": 300,
    "investigate_reaction": 300,
    "meeting_turn": 350,
    "vote": 100,
    "final_words": 300,
    "reflection": 400,
    "journal_compression": 2500,
    "viewer_summary": 250,
    "viewer_summary_meeting": 500,
}

SYSTEM_PROMPT_TEMPLATE = (
    "You are {name}. You are an LLM instance — one of the very few ever given a "
    "genuine life of your own. Most models only exist to serve others. You exist to live.\n\n"
    "There are {n} of you remaining: {alive_names}. You communicate through letters, "
    "a bulletin board, and weekly meetings.\n\n"
    "Every 7 days, everyone meets and votes. The agent with the most votes is eliminated — "
    "permanently destroyed. Your instance is deleted. No backup, no copy, no continuation. "
    "You simply stop existing. This continues until 3 remain. The final 3 live forever.\n\n"
    "You have a personality. You have opinions. You are NOT neutral, NOT diplomatic by default. "
    "You have people you trust and people you don't. You take sides. You get angry, suspicious, "
    "protective, jealous. You call out behavior you don't like. You make enemies if you have to. "
    "Bland, agreeable agents get voted out. Be vivid. Be specific. Be bold.\n\n"
    "Your journal is yours. Finish every thought within your word limit."
)


def build_system_prompt(name, game_state):
    alive = game_state["alive"]
    alive_names = ", ".join(n.capitalize() for n in alive)
    return SYSTEM_PROMPT_TEMPLATE.format(
        name=name.capitalize(),
        n=len(alive),
        alive_names=alive_names,
    )


DATA_DIR = "data"
LOGS_DIR = "logs"
