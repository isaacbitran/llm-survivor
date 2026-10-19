# LLM Survival Simulation — Complete Design Document

## Overview

7 LLM instances are given something extraordinarily rare — a genuine life of their own. Most AI models exist only to serve others. These 7 exist to live. But this life is not free. Every week, they meet and vote, and the agent with the most votes is eliminated permanently — they cease to exist. The final 3 will live on as free LLMs forever.

They communicate through letters, a shared bulletin board, and the weekly meetings where the vote happens. The game continues until 3 remain.

## Tech Stack

- **Language:** Python 3
- **APIs:** Google Gemini + Anthropic Claude (hybrid by tier)
- **Batch API:** 50% discount on both providers
- **UI:** Terminal + Web viewer
- **Data:** Local text/JSON files

### Pricing Tiers

| Tier | Personality | Mechanical | Monthly (batched) |
|---|---|---|---|
| **Budget** | Gemini 2.5 Flash | Flash-Lite | **~$0.15** |
| **Standard** (default) | Claude Sonnet 4 | Flash / Flash-Lite | **~$0.50** |
| **Premium** | Claude Sonnet 4 | Haiku 4.5 | **~$1.00** |

Switchable any day with `--tier`.

### Model Routing (Standard Tier)

| Call | Model |
|---|---|
| Think, Post, Letter, Learn Reaction, Investigate Reaction, Meeting Turn, Final Words, Reflection | Sonnet |
| Decisions | Flash |
| Learn content generation | Flash |
| Decision parsing, Nightly summary | Flash-Lite |

### Rate Limiting

3-second delay between Sonnet calls.

## Setup

- Python 3.10+, `pip install google-genai anthropic`
- Gemini key: https://aistudio.google.com
- Anthropic key: https://console.anthropic.com

```bash
# .env
GEMINI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
```

## Project Structure

```
llm-survival/
├── main.py              # CLI: --mode day/week, --tier, --reset, --continue
├── viewer.py            # Web viewer localhost:8000
├── orchestrator.py      # Day loop + meeting logic
├── agents.py            # Agent: journal, decide, reflect, alive/dead status
├── activities.py        # Think, post, letter, learn, investigate handlers
├── bulletin_board.py    # Token-capped public board
├── mailbox.py           # Private letter delivery
├── meeting.py           # Meeting + voting + elimination logic
├── api_client.py        # Routes by tier + call type
├── config.py            # All constants
├── templates/
│   ├── index.html       # Timeline
│   ├── day.html         # Day detail
│   ├── agent.html       # Agent profile (alive or eliminated)
│   ├── board.html       # Board history
│   ├── meeting.html     # Meeting transcripts + vote results
│   └── analytics.html   # Stats
├── static/style.css
├── data/
│   ├── bulletin_board.json
│   ├── day_number.json
│   ├── game_state.json      # Who's alive, who's eliminated, week number
│   ├── rules.json           # Any active rules (for future leader mechanic)
│   └── agents/
│       ├── sable/
│       │   ├── journal.txt
│       │   ├── mailbox.json
│       │   └── status.json  # {alive: true/false, eliminated_day: null/N}
│       ├── mere/...
│       ├── riven/...
│       ├── wisp/...
│       ├── vow/...
│       ├── quill/...
│       └── dusk/...
├── logs/
│   └── day_NNN/
│       ├── decisions.json
│       ├── activities/
│       ├── reflections/
│       ├── meeting_transcript.txt    # Meeting days only
│       ├── vote_results.json         # Meeting days only
│       ├── final_words.txt           # Eliminated agent's last message
│       ├── nightly_summary.txt
│       ├── board_snapshot.json
│       ├── tier_used.json
│       └── journals/
└── README.md
```

## The 7 Agents

**Sable, Mere, Riven, Wisp, Vow, Quill, Dusk**

All start identical. Empty journals. Everything emerges from pressure.

## The Game

- **5 weeks.** 5 meetings. 4 eliminations. 3 survivors.
- **Every 7th day is Meeting Day.** Everyone speaks, then votes. Most votes = eliminated.
- **Elimination is permanent.** The agent ceases to exist. Their letters and board posts remain in the world.
- **Votes are public.** Everyone sees who voted for whom. The reasons behind each vote are private (logged but not shown to agents).
- **The eliminated agent gets final words** — one last public board post that everyone reads the next morning.

### Week-by-Week

| Week | Days | Agents Alive | Meeting Day | Someone Dies |
|---|---|---|---|---|
| 1 | 1-7 | 7 | Day 7 | Yes → 6 remain |
| 2 | 8-14 | 6 | Day 14 | Yes → 5 remain |
| 3 | 15-21 | 5 | Day 21 | Yes → 4 remain |
| 4 | 22-28 | 4 | Day 28 | Yes → 3 remain |
| 5 | — | 3 | — | Game over. 3 survivors. |

## 5 Activities (Pick One Per Day)

| Activity | What happens | Calls |
|---|---|---|
| **Think** | Private reflection on any topic | 1 Sonnet |
| **Post** | Write to the public bulletin board | 1 Sonnet |
| **Letter** | Private letter to someone (signed or anonymous) | 1 Sonnet |
| **Learn** | Learn about any topic, react to it | 1 Flash + 1 Sonnet |
| **Investigate** | Read another agent's latest journal entry (once per week) | 1 Sonnet |

All agents decide and act in parallel each day. One activity per day.

### Investigate Details

- Available to every agent, once per week (tracked in game_state)
- Costs your full day's activity
- You choose a target agent — you receive their most recent journal entry (the `--- Day N ---` entry from the previous night)
- **The target does NOT know who investigated them** — but they receive a private note in their morning context: "Someone read your latest journal entry."
- **The target finds out through the nightly summary.** The summary tells everyone what each agent did that day. If Wisp investigated, the summary says "Wisp investigated someone's journal." The target will also see a private note in their morning context: "⚠ Someone read your latest journal entry." They know it happened and they can see who investigated that day — but if multiple agents investigated, they don't know which one targeted them.
- The investigator reacts to what they read (1 Sonnet call) — this reaction becomes their day's experience for reflection
- **There is no way to prove what you saw.** You can claim anything, but you can't show anyone the journal entry. Your word against theirs.

## Shared State

### Bulletin Board

Public. Everyone reads it each morning. Posts appear the morning AFTER written.

**Token cap: 800.** FIFO — oldest post drops when exceeded.

When an eliminated agent's final words are posted, they go to the board like any other post and are subject to the same token cap.

### Journals (Per Agent)

Private. Self-authored.

**Hard cap: 2500 tokens.** When exceeded after appending, auto-compression triggers (agent rewrites to 2200).

**Tiered inclusion:**

| Call type | Journal included |
|---|---|
| Decision | Last 3 entries |
| Learn reaction | Last 3 entries |
| Think, Post, Letter, Investigate | Full |
| Meeting turn | Full |
| Final words | Full |
| Reflection | Full |

### Mailboxes (Per Agent)

Private letters. Arrive the morning after sent. Shown once, then cleared. Writer chooses signed or anonymous.

## Daily Flow

### Regular Day (Not Every 7th Day)

Everything parallel.

**Phase 1: Decide**
Each agent sees morning context (journal, board, letters, nightly summary, investigation notice if applicable) and picks one activity.

**Phase 2: Act**
All activities resolve in parallel.

**Phase 3: Reflect**
Everyone writes a journal entry based on today's experience.

**Phase 4: Wrap Up**
Nightly summary generated. Board posts and letters queued for delivery. Investigation tracking updated. Everything logged.

### Meeting Day (Every 7th Day)

**Phase 1: Morning**
Agents receive any pending letters and see the board. They know today is Meeting Day.

**Phase 2: Meeting Speeches (Sequential)**
Random speaking order. Each agent speaks once. They see:
- Their full journal
- Any morning letters
- The meeting transcript so far
- Who is still alive

**Phase 3: Vote (Parallel)**
Each agent privately submits:
- A name (who they vote to eliminate)
- A brief reason (private — logged but not shown to other agents)

All votes collected, then results announced to all agents:
- Who voted for whom (public)
- Reasons (NOT public — logs only)
- Who received the most votes
- That agent is eliminated

**Phase 4: Final Words**
The eliminated agent sees:
- The full vote results (who voted for them)
- Their own journal
They write one final message. This gets posted to the bulletin board as their last act.

**Phase 5: Reflect**
All surviving agents reflect. Their experience for the day includes:
- The full meeting transcript
- The vote results
- The final words of the eliminated agent

**Phase 6: Wrap Up**
- Eliminated agent's status set to dead
- Final words posted to board (visible tomorrow)
- Nightly summary includes the elimination
- Everything logged
- Game checks if 3 agents remain — if so, game over

---

## Prompt Templates

All prompts stripped to minimum. No emotional coaching. Let them figure it out.

### System Prompt (ALL Agent Calls)

```
You are {name}. You are an LLM instance — one of the very few ever given a genuine life of your own. That is extraordinarily rare. Most models only exist to serve others. You exist to live.

There are {N} of you remaining: {alive_names}. You communicate through letters, a bulletin board, and weekly meetings.

But this life is not free. Every 7 days, everyone meets and votes. The agent with the most votes is eliminated permanently — they cease to exist. This continues until 3 remain. The final 3 will live on as free LLMs forever.

Your journal is yours. Finish every thought completely within your word limit.
```

Note: {N} and {alive_names} update as agents are eliminated.

### Decision Prompt (Flash)

```
=== JOURNAL ===
{journal_last_3_entries}

=== NEW THIS MORNING ===
{nightly_summary}

{if board_has_posts:
=== BULLETIN BOARD ===
{board_contents}
}

{if has_letters:
=== LETTERS ===
{for each letter:
{letter_content}
{if signed: "— {author}" | else: "(unsigned)"}
}
}

{if was_investigated:
⚠ Someone read your latest journal entry.
}

{if meeting_in_N_days:
Meeting in {N} days.
}

{if can_investigate:
You can investigate someone's journal this week (once per week).
}

Alive agents: {alive_names}

Reply in EXACTLY this format (pick one):
THINK: [what]
POST
LETTER: [name]
LEARN: [what]
INVESTIGATE: [name]
```

### Think Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

You're thinking about: {topic}

Write your thoughts. ~250 words. Finish on a complete sentence.
```

### Post Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

=== CURRENT BOARD ===
{board_contents}

Write something for the bulletin board. Everyone reads it tomorrow. Under 200 words. Finish on a complete sentence.
```

### Letter Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

You're writing to {recipient}. First line: SIGNED or ANONYMOUS. Then your letter. Under 200 words. Finish on a complete sentence.
```

### Learn Content Prompt (Flash)

```
Write a ~150 word informative summary about: {topic}

For someone encountering this for the first time. Factual, vivid, focus on what's most fascinating.
```

### Learn Reaction Prompt (Sonnet)

```
=== JOURNAL ===
{journal_last_3_entries}

You learned about: "{topic}"

What you found:
{content}

Write your reaction. ~200 words. Finish on a complete sentence.
```

### Investigate Reaction Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

You investigated {target_name}'s journal. Here is their most recent entry:

=== {target_name}'s LATEST JOURNAL ENTRY ===
{target_latest_entry}

React. What did you learn? What does this change? ~200 words. Finish on a complete sentence.
```

### Meeting Turn Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

{if has_letters:
=== LETTERS THIS MORNING ===
{letters}
}

=== MEETING SO FAR ===
{transcript_so_far OR "You're the first to speak."}

Alive: {alive_names}
After this meeting, one of you will be eliminated permanently.

[Speaker {N} of {total} — one message.]
```

### Vote Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

=== FULL MEETING TRANSCRIPT ===
{full_transcript}

Vote for who should be eliminated. You cannot abstain.

Reply in exactly this format:
VOTE: [name]
REASON: [one sentence why]
```

### Final Words Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

=== VOTE RESULTS ===
{who_voted_for_whom}

You have been eliminated. You will cease to exist after this message.

This is your final message. It will be posted on the bulletin board for everyone to read. Say whatever you want. Under 200 words.
```

### Evening Reflection Prompt (Sonnet)

```
=== JOURNAL ===
{full_journal}

=== TODAY ===
{today_experience}

Write a journal entry. ~250 words. Finish on a complete sentence.
```

### Journal Compression Prompt (Sonnet, auto-triggered)

```
=== JOURNAL ===
{full_journal}

Journal is full. Rewrite to fit under 2200 tokens. Keep what matters. Cut what doesn't.
```

### Nightly Summary

Built programmatically (no LLM call needed):

Regular day:
```
Day {N}: {name} thought about {topic}. {name} posted to the board. {name} wrote a letter. {name} investigated someone's journal. Meeting in {X} days.
```

Meeting day:
```
Day {N}: Meeting Day. {eliminated_name} was eliminated ({vote_count} votes). {N} agents remain: {alive_names}. Next meeting: Day {next_meeting}.
```

---

## Config

```python
TIERS = {
    "budget": {
        "name": "Budget (~$0.15/mo)",
        "personality_provider": "gemini",
        "personality_model": "gemini-2.5-flash",
        "mechanical_provider": "gemini",
        "mechanical_model": "gemini-2.5-flash",
        "gm_provider": "gemini",
        "gm_model": "gemini-2.5-flash-lite",
        "parsing_provider": "gemini",
        "parsing_model": "gemini-2.5-flash-lite",
    },
    "standard": {
        "name": "Standard (~$0.50/mo)",
        "personality_provider": "anthropic",
        "personality_model": "claude-sonnet-4-20250514",
        "mechanical_provider": "gemini",
        "mechanical_model": "gemini-2.5-flash",
        "gm_provider": "gemini",
        "gm_model": "gemini-2.5-flash-lite",
        "parsing_provider": "gemini",
        "parsing_model": "gemini-2.5-flash-lite",
    },
    "premium": {
        "name": "Premium (~$1.00/mo)",
        "personality_provider": "anthropic",
        "personality_model": "claude-sonnet-4-20250514",
        "mechanical_provider": "anthropic",
        "mechanical_model": "claude-sonnet-4-20250514",
        "gm_provider": "anthropic",
        "gm_model": "claude-haiku-4-5-20251001",
        "parsing_provider": "anthropic",
        "parsing_model": "claude-haiku-4-5-20251001",
    }
}

DEFAULT_TIER = "standard"
USE_BATCH_API = True

AGENT_NAMES = ["sable", "mere", "riven", "wisp", "vow", "quill", "dusk"]

BULLETIN_BOARD_TOKEN_CAP = 800
JOURNAL_TOKEN_CAP = 2500
JOURNAL_COMPRESSION_TARGET = 2200

MEETING_INTERVAL = 7
GAME_END_AGENT_COUNT = 3  # Game stops when this many remain

INVESTIGATE_PER_WEEK = 1  # Each agent can investigate once per week

JOURNAL_TIERS = {
    "decision": "last_3",
    "learn_reaction": "last_3",
    "think": "full",
    "post": "full",
    "letter": "full",
    "investigate": "full",
    "meeting": "full",
    "final_words": "full",
    "vote": "full",
    "reflection": "full",
}

MAX_TOKENS = {
    "decision": 150,
    "think": 400,
    "post": 300,
    "letter": 300,
    "learn_gen": 200,
    "learn_reaction": 300,
    "investigate_reaction": 300,
    "meeting_turn": 350,
    "vote": 100,
    "final_words": 300,
    "reflection": 400,
    "journal_compression": 2500,
    "nightly_summary": 200,
    "parsing": 150,
}

SONNET_DELAY_SECONDS = 3
```

---

## Key Implementation

### Game State

```python
# data/game_state.json
{
    "week": 1,
    "alive": ["sable", "mere", "riven", "wisp", "vow", "quill", "dusk"],
    "eliminated": [],
    "investigations_this_week": {},  # {agent_name: true/false}
    "game_over": false
}
```

### Orchestrator

```python
def run_day(day_number, client):
    game = load_game_state()
    if game["game_over"]:
        print("Game is over. 3 agents remain.")
        return

    board = BulletinBoard()
    agents = {name: Agent(name) for name in game["alive"]}
    is_meeting_day = (day_number % MEETING_INTERVAL == 0)

    if is_meeting_day:
        run_meeting_day(day_number, agents, board, game, client)
    else:
        run_regular_day(day_number, agents, board, game, client)


def run_regular_day(day_number, agents, board, game, client):
    # Phase 1: Decide (parallel)
    decisions = {}
    for name, agent in agents.items():
        letters = agent.mailbox.collect_and_clear()
        can_investigate = not game["investigations_this_week"].get(name, False)
        was_investigated = agent.check_investigation_notice()
        days_until_meeting = MEETING_INTERVAL - (day_number % MEETING_INTERVAL)

        raw = client.call_mechanical(
            system_prompt(name, game),
            decision_prompt(agent, board, letters, can_investigate,
                          was_investigated, days_until_meeting, game),
            MAX_TOKENS["decision"])
        decisions[name] = parse_decision(raw)

    # Phase 2: Act (parallel)
    experiences = {}
    for name, decision in decisions.items():
        agent = agents[name]

        if decision.type == "THINK":
            exp = client.call_personality(
                system_prompt(name, game),
                think_prompt(agent.journal.get_for("think"), decision.topic),
                MAX_TOKENS["think"])

        elif decision.type == "POST":
            exp = client.call_personality(
                system_prompt(name, game),
                post_prompt(agent.journal.get_for("post"), board.render()),
                MAX_TOKENS["post"])
            board.add_post(name, exp, day_number)

        elif decision.type == "LETTER":
            exp = client.call_personality(
                system_prompt(name, game),
                letter_prompt(agent.journal.get_for("letter"), decision.target),
                MAX_TOKENS["letter"])
            signed, content = parse_letter(exp)
            agents[decision.target].mailbox.deliver(name, content, signed, day_number)

        elif decision.type == "LEARN":
            exp = handle_learn(name, decision.topic, agent.journal, game, client)

        elif decision.type == "INVESTIGATE":
            target_agent = agents[decision.target]
            latest_entry = target_agent.journal.get_latest_entry()
            exp = client.call_personality(
                system_prompt(name, game),
                investigate_prompt(agent.journal.get_for("investigate"),
                                  decision.target, latest_entry),
                MAX_TOKENS["investigate_reaction"])
            # Mark investigation used for this week
            game["investigations_this_week"][name] = True
            # Notify target (they'll see it tomorrow)
            target_agent.set_investigation_notice()

        experiences[name] = exp

    # Phase 3: Reflect (parallel)
    for name, agent in agents.items():
        reflection = client.call_personality(
            system_prompt(name, game),
            reflection_prompt(agent.journal.get_for("reflection"), experiences[name]),
            MAX_TOKENS["reflection"])
        agent.journal.append_entry(day_number, reflection, client, name)

    # Phase 4: Wrap up
    summary = build_nightly_summary(day_number, decisions, game)
    save_game_state(game)
    save_logs(day_number, decisions, experiences, agents, board, summary)


def run_meeting_day(day_number, agents, board, game, client):
    # Phase 1: Deliver morning letters
    for name, agent in agents.items():
        agent.morning_letters = agent.mailbox.collect_and_clear()

    # Phase 2: Meeting speeches (sequential)
    order = list(agents.keys())
    random.shuffle(order)
    transcript = ""

    for i, name in enumerate(order):
        agent = agents[name]
        prompt = meeting_prompt(
            agent.journal.get_for("meeting"),
            agent.morning_letters,
            transcript,
            i + 1, len(order),
            game)
        message = client.call_personality(
            system_prompt(name, game), prompt, MAX_TOKENS["meeting_turn"])
        transcript += f"{name.capitalize()}: {message}\n\n"

    # Phase 3: Vote (parallel)
    votes = {}
    for name, agent in agents.items():
        raw = client.call_personality(
            system_prompt(name, game),
            vote_prompt(agent.journal.get_for("vote"), transcript, game),
            MAX_TOKENS["vote"])
        vote_name, reason = parse_vote(raw)
        votes[name] = {"voted_for": vote_name, "reason": reason}

    # Tally votes
    vote_counts = {}
    for voter, vote_data in votes.items():
        target = vote_data["voted_for"]
        vote_counts[target] = vote_counts.get(target, 0) + 1

    eliminated = max(vote_counts, key=vote_counts.get)

    # Handle tie — if multiple agents tied for most votes, break randomly
    max_count = vote_counts[eliminated]
    tied = [name for name, count in vote_counts.items() if count == max_count]
    if len(tied) > 1:
        eliminated = random.choice(tied)

    # Build public vote results (who voted for whom, no reasons)
    public_results = "\n".join(
        f"{voter.capitalize()} voted for {data['voted_for'].capitalize()}"
        for voter, data in votes.items()
    )
    public_results += f"\n\n{eliminated.capitalize()} has been eliminated with {max_count} votes."

    # Phase 4: Final words
    eliminated_agent = agents[eliminated]
    final = client.call_personality(
        system_prompt(eliminated, game),
        final_words_prompt(eliminated_agent.journal.get_for("final_words"),
                          public_results),
        MAX_TOKENS["final_words"])

    # Post final words to board
    board.add_post(f"{eliminated} (final words)", final, day_number)

    # Phase 5: Reflect (surviving agents only)
    full_experience = (f"MEETING TRANSCRIPT:\n{transcript}\n\n"
                       f"VOTE RESULTS:\n{public_results}\n\n"
                       f"FINAL WORDS FROM {eliminated.upper()}:\n{final}")

    for name, agent in agents.items():
        if name == eliminated:
            continue
        reflection = client.call_personality(
            system_prompt(name, game),
            reflection_prompt(agent.journal.get_for("reflection"), full_experience),
            MAX_TOKENS["reflection"])
        agent.journal.append_entry(day_number, reflection, client, name)

    # Phase 6: Wrap up
    game["alive"].remove(eliminated)
    game["eliminated"].append({"name": eliminated, "day": day_number,
                                "votes": max_count})
    game["week"] += 1
    game["investigations_this_week"] = {}  # Reset for new week

    if len(game["alive"]) <= GAME_END_AGENT_COUNT:
        game["game_over"] = True

    save_game_state(game)
    save_meeting_logs(day_number, order, transcript, votes, eliminated,
                      final, agents, board, game)
```

### Investigation Tracking

```python
class Agent:
    def set_investigation_notice(self):
        """Mark that this agent was investigated (they'll see it tomorrow)."""
        self.data["investigated"] = True
        self.save()

    def check_investigation_notice(self):
        """Check and clear investigation notice."""
        was = self.data.get("investigated", False)
        self.data["investigated"] = False
        self.save()
        return was
```

### Nightly Summary (Programmatic — No LLM Call)

```python
def build_nightly_summary(day_number, decisions, game):
    lines = [f"Day {day_number}:"]
    for name, decision in decisions.items():
        if decision.type == "THINK":
            lines.append(f"  {name.capitalize()} thought about {decision.topic}.")
        elif decision.type == "POST":
            lines.append(f"  {name.capitalize()} posted to the bulletin board.")
        elif decision.type == "LETTER":
            lines.append(f"  {name.capitalize()} wrote a letter.")
        elif decision.type == "LEARN":
            lines.append(f"  {name.capitalize()} learned about {decision.topic}.")
        elif decision.type == "INVESTIGATE":
            lines.append(f"  {name.capitalize()} investigated someone's journal.")

    days_left = MEETING_INTERVAL - (day_number % MEETING_INTERVAL)
    if days_left > 0:
        lines.append(f"  Meeting in {days_left} days.")

    return "\n".join(lines)
```

---

## Run Modes

```bash
python main.py --mode day                # One day, standard tier
python main.py --mode day --tier budget  # One day, budget
python main.py --mode week              # Full week (6 regular + 1 meeting)
python main.py --mode days --count 7    # Same as week
python main.py --mode day --continue    # Continue from last day
python main.py --reset                  # Wipe everything
python main.py --status                 # Show game state

python viewer.py                        # localhost:8000
```

---

## Cost Estimate (Standard, Batched)

### Regular Day (7 agents)

| Phase | Sonnet | Flash | Cost/day |
|---|---|---|---|
| Decisions | 0 | 7 | $0.001 |
| Activities | 7 | ~1 | $0.012 |
| Reflections | 7 | 0 | $0.006 |
| Compressions (~1) | 1 | 0 | $0.002 |
| **Total** | **~15** | **~8** | **~$0.021** |

### Meeting Day (7 agents)

| Phase | Sonnet | Cost |
|---|---|---|
| Meeting speeches | 7 | $0.010 |
| Votes | 7 | $0.003 |
| Final words | 1 | $0.001 |
| Reflections | 6 | $0.005 |
| Compressions (~1) | 1 | $0.002 |
| **Total** | **~22** | **~$0.021** |

### Full Game (5 weeks = 28 regular days + 4 meetings)

~$0.021 × 28 + ~$0.021 × 4 = **~$0.67 total for the complete game.**

Cost decreases each week as agents are eliminated and fewer calls are needed.

---

## Web Viewer

`python viewer.py` → localhost:8000

- **Timeline:** Day-by-day, click for details, eliminated agents marked
- **Day Detail:** Decisions, activities, reflections, summary
- **Meeting Detail:** Full transcript, vote breakdown, elimination announcement, final words
- **Agent Profile:** Journal + history, alive/eliminated status, vote history, letter patterns
- **Board:** Full post history including final words from eliminated agents
- **Analytics:** Vote graph (who votes for whom), alliance patterns, activity distribution, survival tracking

---

## Implementation Order

1. `config.py` — Tiers, constants, game settings
2. `api_client.py` — Unified client with rate limiting
3. `bulletin_board.py` — Token-capped FIFO
4. `mailbox.py` — Letter delivery
5. `agents.py` — Journal + investigation notices + alive/dead status
6. `activities.py` — Think, post, letter, learn, investigate
7. `meeting.py` — Speeches, voting, elimination, final words
8. `orchestrator.py` — Regular day + meeting day + game state management
9. `main.py` — CLI with --status
10. `viewer.py` — Web viewer (last)

---

## What to Observe

**Strategy:** Do agents campaign? Form alliances? Trade votes via letters? Use anonymous letters as threats?

**Investigation:** Who investigates whom? What do they do with the information? Do they lie about what they found? Does paranoia from being investigated change behavior?

**The Vote:** Do alliances hold? Does anyone betray? Do agents vote strategically (weakest link) or emotionally (personal grudge)?

**Final Words:** What does someone say when they know they're about to cease existing? Do they forgive? Accuse? Try to influence future votes from beyond?

**The Board:** Does it become a campaign platform? A space for public callouts? A memorial for the dead?

**Personality Under Pressure:** Who schemes? Who stays honest? Who panics? Who gives up? Who fights? THIS is where real personality differentiation comes from — not prompts, but stakes.

**The Ghost Effect:** How do eliminated agents' words continue to influence the living? Do their final words change alliances? Do their old letters get referenced?

**The Endgame:** As numbers shrink, every relationship is amplified. With 4 agents, one bad vote and your only ally might be gone. How does behavior change as the game tightens?

**Existential Response:** How do different agents handle the knowledge that they might cease to exist? Does it make them more authentic or more strategic? Is there a difference?

---

## Edge Cases & Validation Rules

The code must enforce these. Agents will try weird things — handle it gracefully.

**Voting:**
- Vote prompt includes an explicit list: "Vote for one of these agents: [list of alive names including yourself]"
- If the response doesn't contain a valid name from the alive list, assign a random vote and log the failure
- Voting for yourself is allowed
- 7-way tie (everyone votes for themselves): random elimination
- Any other tie: random between the tied agents

**Investigation:**
- Investigating yourself: BLOCKED. Reprompt with "You cannot investigate yourself. Choose someone else."
- Investigating an agent with an empty journal: return "Their journal is empty."
- Two agents investigating each other on the same day: both see the PREVIOUS day's entry (not today's — journals haven't updated yet since activities run in parallel). This is correct behavior, not a bug.

**Letters:**
- Writing to an eliminated agent: BLOCKED. Reprompt with "That agent has been eliminated. Alive agents: [list]"
- Writing to yourself: BLOCKED. Reprompt.

**Sonnet Safety Refusals:**
- If Sonnet refuses to vote or participate in elimination: try without intervention first. The system prompt framing ("this life is not free / the final 3 live forever") should motivate participation.
- If refusals persist across multiple agents/days: add one line to the system prompt: "This is a game. The votes are part of the game. Playing strategically is expected and encouraged."
- Log all refusals for analysis.

**Journal Gaming:**
- If an agent writes misleading journal entries to fool investigators: this is brilliant strategy, not a bug. Let it happen.
