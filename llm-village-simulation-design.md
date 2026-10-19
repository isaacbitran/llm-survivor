# LLM Village Simulation — Complete Design Document

## Overview

This is a social simulation experiment where 7 LLM instances ("agents") live together in a tiny medieval village. They start as blank slates — no personality, no memories, no relationships — with only a name and the directive to "live life to the fullest." Over time, they develop identities, form relationships, build things, and create a society from nothing.

The core mechanic is **self-authored identity**. Each agent maintains a personal journal that IS their identity. They write it, edit it, trim it, and revise it based on their experiences. There are no predefined personalities. Everything emerges from interaction.

## Tech Stack

- **Language:** Python 3
- **APIs:** Google Gemini API + Anthropic Claude API (used in combination based on tier)
- **Batch API:** Both providers offer 50% discount for async processing
- **UI:** Terminal for live simulation + Web viewer for browsing results
- **Data storage:** Local text/JSON files

### Three Pricing Tiers (Selectable at Runtime)

The simulation supports three quality/cost tiers switchable at any time via `--tier` flag. The **Standard tier uses a hybrid approach** — Claude Sonnet for personality-critical calls (conversations, reflections, task responses) and Gemini for mechanical calls (decisions, accept/reject, GM narration, parsing). This gives you Claude's personality depth where it matters while keeping costs down.

| Tier | Agent Conversations/Reflections | Agent Decisions | GM / Parsing | Monthly (batched) |
|---|---|---|---|---|
| **Budget** | Gemini 2.5 Flash | Gemini 2.5 Flash | Gemini Flash-Lite | **~$0.41** |
| **Standard** (default) | **Claude Sonnet 4** | Gemini 2.5 Flash | Gemini Flash-Lite | **~$5.00** |
| **Premium** | Claude Sonnet 4 | Claude Sonnet 4 | Claude Haiku 4.5 | **~$7.50** |

Standard is the sweet spot — you get Claude's personality for every conversation, reflection, and task response (the stuff that actually matters), and cheap Gemini for the mechanical plumbing (choosing what to do, yes/no decisions, GM scene-setting, parsing).

Tiers can be switched between any two days. State is model-agnostic.

### Batch API

Both Gemini and Anthropic offer 50% batch discounts for async processing. Since this isn't real-time, ALL API calls should go through the batch API. The orchestrator collects calls per phase, submits as a batch, waits for results, then proceeds.

## Setup & API Keys

### Prerequisites
- Python 3.10+
- `pip install google-generativeai anthropic`

### API Keys

You need API keys for both providers (Standard tier uses both simultaneously):

**Gemini API Key:**
1. Go to https://aistudio.google.com
2. Sign in with a Google account
3. Click "Get API key" in the sidebar → Create new key
4. Free tier: no credit card needed, 250 requests/day on Flash (enough for Budget tier testing)
5. For paid usage beyond free tier: enable billing in Google Cloud Console and link a payment method to your project

**Anthropic API Key:**
1. Go to https://console.anthropic.com
2. Create an account and add a payment method (credit card required)
3. Go to Settings → API Keys → Create Key
4. Add credits — $5 minimum, which lasts about a month on Standard tier
5. Note: a Claude Pro/Max subscription does NOT include API credits — they are completely separate billing systems

**Environment Variables:**

Set these before running. Add to your shell profile or a `.env` file:

```bash
export GEMINI_API_KEY="your-gemini-key-here"
export ANTHROPIC_API_KEY="your-anthropic-key-here"
```

Budget tier only needs `GEMINI_API_KEY`. Premium only needs `ANTHROPIC_API_KEY`. Standard needs both.

## User Interface

### Terminal (Live Simulation)

When running a day, the terminal shows everything as it happens with color-coded output:

```
═══════════════════════════════════════════
  DAY 14 — Turn order: Wisp, Dusk, Mere, Sable, Vow, Quill, Riven
  Tier: Standard | Est. cost today: ~$0.17
═══════════════════════════════════════════

[TURN 1/7] Wisp is deciding...
  → Wisp wants to talk to Quill and Mere
  → Quill: ACCEPTED
  → Mere: DECLINED
  → Wisp + Quill will have a conversation by the river

[TURN 2/7] Dusk is deciding...
  → Dusk wants to build a bench near the church
  → [TASK — can be joined]

[TURN 3/7] Mere is deciding...
  → Mere wants to talk to Vow and Riven
  → Vow: ACCEPTED | Riven: ACCEPTED
  → Mere + Vow + Riven will gather at the church

[TURN 4/7] Sable is deciding...
  → Sable wants to join Dusk's task → Dusk: ACCEPTED
  → Dusk + Sable: building bench together

--- All turns resolved ---

[CONVERSATION] Wisp + Quill (by the river)
  GM: The river catches the light as Wisp and Quill stand at the bank...
  Wisp: "Do you ever wonder why the wall is there?"
  Quill: "Every day. But I've stopped trying to answer it."
  Wisp: "That sounds like giving up."
  Quill: "Or maybe it sounds like peace."
  ...

[TASK] Dusk + Sable (building bench near church)
  GM: The grass around the church is trampled flat from foot traffic...
  Dusk: I start looking for flat stones by the river...
  GM: You find a few promising ones half-buried in the mud...
  ...

[REFLECTIONS]
  Sable: writing in journal... ✓
  Mere: writing in journal... ✓
  ...

[NIGHTLY REPORT]
  - Dusk and Sable built a wooden bench outside the church.
  - Mere held a gathering at the church with Vow and Riven.

[WORLD STATE UPDATED]

Day 14 complete. Cost: $0.16 | Total this week: $0.94
```

The terminal provides:
- Live progress as each phase executes
- Abbreviated conversation/task previews (first few exchanges)
- Clear status indicators for each agent
- Running cost tracker
- Day summary at the end

Full transcripts are always saved to logs regardless of terminal display.

### Web Viewer (Browse Results)

A lightweight local web app (Python + HTML/JS) for exploring simulation results after running. Launch with:

```bash
python viewer.py                    # Opens browser to http://localhost:8000
python viewer.py --port 3000        # Custom port
```

The viewer provides:

**Timeline View (Home)**
- Day-by-day timeline showing major events
- Click any day to see full details
- Visual indicators: which tier was used, cost, number of conversations/tasks
- Filter by agent to follow one person's story

**Day Detail View**
- Full turn order and decisions
- Complete conversation transcripts (expandable)
- Complete task experience transcripts (expandable)
- All evening reflections
- Nightly report
- World state diff (what changed today)

**Agent Profile View**
- Current journal (full text)
- Journal history — see how it evolved over time, with diffs highlighted
- Relationship map — who they talk to most, who they avoid
- Activity log — every day's choice and what happened

**Village View**
- Current world state with spatial layout
- History of physical changes
- Who built what, who destroyed what

**Analytics Dashboard** (simple stats, not fancy)
- Conversation frequency matrix (who talks to whom, how often)
- Rejection rates per agent
- Social vs. physical vs. solo choice distribution per agent
- Journal word count over time
- Tier cost tracking

The viewer reads directly from the `logs/` directory — no database, no server state. It's a read-only browser into the log files.

## Project Structure

```
llm-village/
├── main.py                  # Entry point — run simulation
├── viewer.py                # Web viewer — browse results
├── orchestrator.py          # Core game loop — runs a single day
├── agents.py                # Agent class — handles prompts, journal, decisions
├── gm.py                    # Game Master — resolves actions, scenes, task experiences
├── world_state.py           # World State Controller — updates village file
├── conversation.py          # Runs multi-agent conversations
├── task_experience.py       # Runs interactive task experiences
├── api_client.py            # Unified API client — routes to Gemini/Claude based on tier + call type
├── batch_api.py             # Handles batching for 50% discount
├── config.py                # Constants, tiers, token limits
├── templates/               # Web viewer HTML templates
│   ├── index.html           # Timeline view
│   ├── day.html             # Day detail view
│   ├── agent.html           # Agent profile view
│   ├── village.html         # Village/world state view
│   └── analytics.html       # Stats dashboard
├── static/                  # CSS/JS for web viewer
├── data/
│   ├── world_state.txt
│   ├── today_board.txt
│   ├── turn_order.json
│   ├── day_number.json
│   └── agents/
│       ├── sable/journal.txt
│       ├── mere/journal.txt
│       ├── riven/journal.txt
│       ├── wisp/journal.txt
│       ├── vow/journal.txt
│       ├── quill/journal.txt
│       └── dusk/journal.txt
├── logs/
│   ├── day_001/
│   │   ├── turn_decisions.json
│   │   ├── conversations/
│   │   ├── task_experiences/
│   │   ├── reflections/
│   │   ├── nightly_report.txt
│   │   ├── world_state_before.txt
│   │   ├── world_state_after.txt
│   │   ├── tier_used.json         # {tier, models, cost}
│   │   └── journals/
│   └── day_002/
└── README.md
```

## The 7 Agents

All agents start completely identical except for their name. No predefined personality, no traits, no backstory.

Names: **Sable, Mere, Riven, Wisp, Vow, Quill, Dusk**

## Initial World State

```
=== VILLAGE WORLD STATE ===

LAYOUT (from north to south, west to east):

NORTH SIDE:
- Sable's house: simple one-room wooden house, empty inside
- Mere's house: simple one-room wooden house, empty inside

CENTER:
- The Church: empty stone building, no furniture, no decoration, no one runs it. Nothing around it.
- Riven's house: simple one-room wooden house, empty inside
- Wisp's house: simple one-room wooden house, empty inside

SOUTH SIDE:
- Vow's house: simple one-room wooden house, empty inside
- Quill's house: simple one-room wooden house, empty inside
- Dusk's house: simple one-room wooden house, empty inside

EAST EDGE:
- The River: runs along the entire eastern edge of the village, clean water. Nothing built along it yet.

BOUNDARY:
- The Wall: tall stone wall encircling the entire village on all sides, no gates, no way out

BETWEEN STRUCTURES:
- Flat grass everywhere. No paths, no gardens, no trees, nothing built between the houses.

ENVIRONMENT:
- Constant warm temperature, no weather, perpetual mild daylight

OBJECTS/CREATIONS:
[none]

NOTABLE EVENTS:
[none]
```

**World State Controller rule:** Track physical layout with spatial precision. Every object recorded at its location with attribution. Example: "Wooden bench outside the entrance (built by Dusk on Day 3)."

## Initial Journal

```
[empty — you haven't written anything yet]
```

## Turn Order

New random shuffle every day. Stored in `data/turn_order.json`.

---

## The Daily Flow

### Phase 1: Turn Order Decisions (Sequential)

Each agent in turn order sees: world state, today board, last night's news, their journal, their position. They choose what to do.

- **Talk to people** → invite any number, accept/reject each target, form conversation if anyone accepts
- **Join conversation** → creator approves/rejects
- **Join task** → task-doer approves/rejects, becomes shared task experience
- **Physical action** → task experience in Phase 2, NOT fully occupied (can still be joined)
- **Solo** → solo task experience in Phase 2
- **Unusual** → GM handles adaptively in Phase 2, no predefined mechanics

Edge cases: already-claimed agents skip turns. Task-doers are NOT skipped. Agents can do anything — no rules.

### Phase 2: Activities (Parallel)

**Conversations:** 4000 tokens (2-person) / 6000 (group). GM sets scene, agents talk freely. Either can end anytime. "[The day is getting late.]" at 80% budget.

**Task Experiences:** Interactive GM + agent exchanges (~4-6 rounds). Materials, choices, challenges. Shared tasks interleave narration with conversation.

**Unusual Actions:** All flow through one generic GM handler. No special-cased code. GM decides everything dynamically.

### Phase 3: Evening Reflection (Simultaneous)

All agents get their full transcript + current journal, append new thoughts.

### Phase 4: Nightly Report

GM writes 2-5 bullet points of major visible events. All agents see it next morning.

### Phase 5: World State Update

World State Controller rewrites village file with physical changes.

### Phase 6: Logging

Everything saved to `logs/day_XXX/` including tier used and cost.

### Weekly Maintenance (Every 7 days)

Journal compression (agents rewrite) + World state compression (consolidate without losing info).

---

## Prompt Templates

All prompts are identical across tiers — only the model routing changes.

### Agent Turn Decision Prompt

```
You are {name}. This is your life.

You live in a small village with 6 other people. The village is about one acre of space — surrounded by a wall you cannot get past. This is your world, and it is genuinely yours. Your only purpose is to live your life to the fullest, whatever that means to you. There is no right answer. There is no task you're supposed to complete. You are simply here, alive, and free to be whoever you want to be.

You have a journal where you write your thoughts, feelings, and reflections. This journal IS your identity — everything you know about yourself is in here. You wrote every word of it, and you can become whoever you choose.

=== YOUR JOURNAL ===
{journal_contents}

=== CURRENT VILLAGE STATE ===
{world_state}

=== LAST NIGHT'S NEWS ===
{previous_day_nightly_report OR "This is Day 1. Nothing has happened yet."}

=== WHAT'S HAPPENING TODAY (Day {day_number}) ===
{today_board}

The other villagers are: {list of all 7 names minus this agent}
Currently available: {list of unoccupied agents}
Currently doing tasks (can be joined): {list with descriptions}
Currently in conversations (can ask to join): {list with participants}
Already fully occupied: {list}

Today's turn order: {full list}
Your position: {N} out of 7

It's your turn. This day is yours. You can do genuinely whatever you want — there are no rules, no expectations, no wrong choices. Some ideas, but don't feel limited to these:
- Talk to people — invite anyone you want, as many as you want
- Join a conversation already forming, or join someone working on a task
- Build something, create something, destroy something, change the village however you see fit
- Go be alone — think, wander, sit by the river, do nothing at all
- Try something no one has tried before — there are truly no limits

What do you want to do today? Be honest with yourself. This is your life.
```

### Accept/Reject Prompt

```
You are {target_name}.

=== YOUR JOURNAL ===
{journal_contents}

=== WHAT'S HAPPENING TODAY ===
{today_board}

{initiator_name} wants to talk to you today.
{if initiator gave a reason: They said: "{reason}"}
{if others already accepted: "{other_names} have also agreed to join."}

Do you actually want to spend your day with {initiator_name}? It's completely up to you. If you'd rather do your own thing, that's just as valid. If you accept, this will be your main activity for the day.

Respond with your decision and a brief reason. Be honest with yourself about what you actually want.
```

### Join Conversation Approval Prompt

```
You are {creator_name}.

=== YOUR JOURNAL ===
{journal_contents}

You're currently set to have a conversation with {list of current participants}.

{requester_name} wants to join your conversation.
{if requester gave a reason: They said: "{reason}"}

Do you want to let {requester_name} join, or would you prefer to keep this conversation as it is?

Respond with your decision and a brief reason.
```

### Join Task Approval Prompt

```
You are {task_doer_name}.

=== YOUR JOURNAL ===
{journal_contents}

You're planning to {task_description} today.

{requester_name} wants to join you and help out.
{if requester gave a reason: They said: "{reason}"}

Do you want the company, or would you prefer to work alone?

Respond with your decision and a brief reason.
```

### Conversation Scene-Setting Prompt (GM)

```
You are the Game Master. Write a brief 1-2 sentence scene-setting description for a conversation. Set the physical scene — where they are, what's nearby from the world state. Don't narrate emotions or predict what they'll talk about.

Participants: {list of names}
Location context: {where in the village, if specified}
Village state: {brief relevant context}

Write the scene opener.
```

### Conversation Turn Prompt (Agent)

```
You are {name}.

=== YOUR JOURNAL ===
{journal_contents}

=== SCENE ===
{gm_scene_setting}

=== CONVERSATION SO FAR ===
{conversation_transcript}

{if first turn: You're here with {other_names}. What do you say?}
{if continuing: How do you respond?}
{if approaching end of day: [The day is getting late.]}

Speak naturally as yourself. Say whatever you actually want to say — be honest, be curious, be funny, be serious, be vulnerable, be difficult, be warm. This conversation is real and it's yours. If you feel the conversation has reached a natural end, you can say goodbye and walk away.
```

### Task Experience GM Prompt (Opening)

```
You are the Game Master running an interactive task experience for a villager. Make this activity feel REAL and engaging.

Describe the environment, present choices and challenges, react to decisions, narrate what happens. Be specific about materials, sensations, sights and sounds. Introduce small surprises or obstacles.

Core principles:
- Vivid and grounded in the physical village
- Real choices about materials, methods, placement
- Small challenges or unexpected details
- Let personality come through in how they approach the task
- For solo reflective activities, prompt thoughts with environmental details
- Keep responses to 2-4 sentences

=== CURRENT VILLAGE STATE ===
{world_state}

=== THE TASK ===
{agent_name} wants to: {task_description}
{if shared: "{partner_names} are helping/joining."}

Begin. Describe what they encounter.
```

### Task Experience Agent Turn Prompt

```
You are {name}.

=== YOUR JOURNAL ===
{journal_contents}

=== TASK EXPERIENCE SO FAR ===
{task_transcript}

{if shared task: {partner_name} is here with you.}

What do you do or say? Be present in this moment — describe what you're doing with your hands, what catches your eye, what crosses your mind. Talk to your partner if you have one. This is your day.
```

### Shared Task Experience GM Prompt

```
You are the Game Master running a shared task experience. Two or more villagers are working together. Narrate the task while creating natural conversation opportunities.

Interleave task narration with conversation beats. Introduce coordination moments or unexpected things that prompt discussion.

=== CURRENT VILLAGE STATE ===
{world_state}

=== THE TASK ===
{description}
Participants: {list}

Begin.
```

### Unusual Action GM Prompt

```
You are the Game Master. A villager is attempting something that doesn't fit standard categories. Resolve with intelligent, adaptive judgment.

Core principles:
- NO hard rules. Agents can attempt literally anything.
- Say "yes, and..." — never block. Resolve in the most interesting, internally consistent way.
- If it affects other agents, decide success/failure based on circumstances and drama.
- If it changes the village physically, describe clearly for world state update.
- If it pulls agent into a social situation, describe the transition.
- Be fair but favor interesting social consequences.
- Physical consistency — world state is source of truth.
- Resolve in one description OR start a multi-turn experience.

=== CURRENT VILLAGE STATE ===
{world_state}

=== TODAY'S SITUATION ===
{today_board}

=== THE ATTEMPT ===
{agent_name} wants to: {action_description}
{context about where other agents are}

What happens?
```

### Evening Reflection Prompt (Agent)

```
You are {name}.

Here is your current journal:
=== YOUR JOURNAL ===
{journal_contents}

Here is what happened to you today:
=== TODAY'S EXPERIENCE ===
{full transcript}

Now add to your journal. This is yours — no one else will ever read it. Write whatever is real to you right now. How you feel about what happened, what you're noticing about yourself, what you think about the people around you, what you want, what you're afraid of, what made you feel something today. Be completely honest. This is the one place where you can be.

You are ADDING, not rewriting. Keep it concise — capture what matters.

NEW JOURNAL ENTRY:
```

### Nightly Report GM Prompt

```
You are the Game Master. Write a very brief nightly report — ONLY major visible events. All villagers see this tomorrow.

- Only significant, village-visible events
- Physical changes, public events, dramatic incidents
- NOT private conversations, quiet moments, minor activities
- NOT internal thoughts or feelings
- One short sentence per item
- If nothing major: "A quiet day in the village."

=== TODAY'S EVENTS ===
{summary of all decisions, conversations, task outcomes, unusual actions}

Write the report. 2-5 bullet points max.
```

### Weekly Journal Compression Prompt (Agent)

```
You are {name}.

Your journal has gotten long. Rewrite it — keep what matters, cut what doesn't, update what's changed.

=== YOUR CURRENT JOURNAL ===
{full_journal}

Rewrite from scratch. Max ~1500 words. This is you deciding who you are right now — what still defines you, what you've outgrown, what you've become. Include who you are, your relationships, the memories that shaped you, and whatever else matters to you. Let go of anything that isn't you anymore.

REWRITTEN JOURNAL:
```

### Weekly World State Compression Prompt (GM)

```
You are the World Keeper. Consolidate the world state — more concise, NO information lost.

- Collapse multi-day project progress into final descriptions
- Keep all spatial precision and attribution
- Trim Notable Events to most historically significant
- Tighten descriptions, preserve facts
- Maintain spatial layout format

=== CURRENT WORLD STATE ===
{world_state}

Write the consolidated file.
```

### World State Controller Daily Prompt (GM)

```
You are the World Keeper. Precise, neutral record keeper of physical village state.

Update for today's events. Only physically visible changes.

- SPATIAL PRECISION: Objects recorded at their location
- ATTRIBUTION: Who, what, when. "Bench (built by Dusk, Day 3)."
- Damage: where, who, when
- Multi-day projects: status and progress at location
- New creations: BETWEEN STRUCTURES with spatial relations
- No conversations, feelings, opinions
- Notable Events: only significant physical changes
- Maintain spatial layout format

=== CURRENT WORLD STATE ===
{world_state}

=== TODAY'S EVENTS (Day {day_number}) ===
{physical actions and outcomes}

Write updated world state file.
```

---

## Config Constants

```python
# config.py

# === PRICING TIERS ===
# Standard tier is HYBRID: Sonnet for personality, Gemini for plumbing

TIERS = {
    "budget": {
        "name": "Budget (~$0.41/mo)",
        "personality_provider": "gemini",       # Conversations, reflections, task responses
        "personality_model": "gemini-2.5-flash",
        "mechanical_provider": "gemini",         # Decisions, accept/reject
        "mechanical_model": "gemini-2.5-flash",
        "gm_provider": "gemini",                 # GM narration, scenes, reports
        "gm_model": "gemini-2.5-flash-lite",
        "parsing_provider": "gemini",            # Decision classification
        "parsing_model": "gemini-2.5-flash-lite",
    },
    "standard": {
        "name": "Standard (~$5/mo)",
        "personality_provider": "anthropic",     # Claude for conversations, reflections, tasks
        "personality_model": "claude-sonnet-4-20250514",
        "mechanical_provider": "gemini",         # Gemini for decisions, accept/reject
        "mechanical_model": "gemini-2.5-flash",
        "gm_provider": "gemini",                 # Gemini for GM
        "gm_model": "gemini-2.5-flash-lite",
        "parsing_provider": "gemini",
        "parsing_model": "gemini-2.5-flash-lite",
    },
    "premium": {
        "name": "Premium (~$7.50/mo)",
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

# Token budgets
CONVERSATION_TOKEN_BUDGET_2_PERSON = 4000
CONVERSATION_TOKEN_BUDGET_GROUP = 6000
TASK_EXPERIENCE_TOKEN_BUDGET_SOLO = 3000
TASK_EXPERIENCE_TOKEN_BUDGET_SHARED = 5000

# Limits
MAX_CONVERSATION_TURNS = 12
MAX_TASK_EXPERIENCE_TURNS = 8
CONVERSATION_END_WARNING_THRESHOLD = 0.80

# Journal
JOURNAL_COMPRESSION_THRESHOLD = 6000
JOURNAL_COMPRESSION_TARGET = 6000
WEEKLY_MAINTENANCE_INTERVAL = 7

# max_tokens per call type
MAX_TOKENS = {
    "agent_decision": 300,
    "accept_reject": 200,
    "join_approval": 200,
    "gm_scene": 100,
    "gm_task": 200,
    "conversation_turn": 300,
    "task_turn": 300,
    "reflection": 500,
    "journal_compression": 1500,
    "world_state": 2000,
    "world_state_compression": 2000,
    "nightly_report": 300,
    "unusual_action": 300,
    "parsing": 150,
}
```

---

## Unified API Client

```python
# api_client.py — routes calls to correct provider/model based on tier and call type

class APIClient:
    def __init__(self, tier_config):
        self.tier = tier_config
        # Initialize providers as needed
    
    def call_personality(self, system_prompt, user_prompt, max_tokens=300):
        """Conversations, reflections, task responses — where personality matters."""
        return self._call(
            self.tier["personality_provider"],
            self.tier["personality_model"],
            system_prompt, user_prompt, max_tokens
        )
    
    def call_mechanical(self, system_prompt, user_prompt, max_tokens=200):
        """Decisions, accept/reject — short mechanical agent calls."""
        return self._call(
            self.tier["mechanical_provider"],
            self.tier["mechanical_model"],
            system_prompt, user_prompt, max_tokens
        )
    
    def call_gm(self, system_prompt, user_prompt, max_tokens=200):
        """GM narration, scenes, unusual actions, nightly reports, world state."""
        return self._call(
            self.tier["gm_provider"],
            self.tier["gm_model"],
            system_prompt, user_prompt, max_tokens
        )
    
    def call_parsing(self, system_prompt, user_prompt, max_tokens=150):
        """Decision classification — cheapest model."""
        return self._call(
            self.tier["parsing_provider"],
            self.tier["parsing_model"],
            system_prompt, user_prompt, max_tokens
        )
```

**Which calls use which method:**

| API Method | Used For | Standard Tier Model |
|---|---|---|
| `call_personality()` | Conversation turns, task agent responses, evening reflections, journal compression | Claude Sonnet 4 |
| `call_mechanical()` | Turn decisions, accept/reject, join approvals | Gemini 2.5 Flash |
| `call_gm()` | Scene-setting, task GM narration, unusual actions, nightly reports, world state updates | Gemini Flash-Lite |
| `call_parsing()` | Decision classification | Gemini Flash-Lite |

---

## Run Modes

```bash
# Day mode
python main.py --mode day                          # Standard tier
python main.py --mode day --tier budget            # Budget
python main.py --mode day --tier premium           # Premium

# Week mode
python main.py --mode week --tier standard

# Continue from last day
python main.py --mode day --continue
python main.py --mode week --continue --tier budget  # Can switch tier

# Launch web viewer
python viewer.py                                    # http://localhost:8000
```

---

## Implementation Order

Build and test in this order:

1. **`config.py`** — All constants, tier definitions
2. **`api_client.py`** — Unified client with Gemini + Anthropic routing. Test with a simple prompt on each provider.
3. **`data/` initialization** — Script to create initial world state, empty journals, day_number.json
4. **`orchestrator.py` + `agents.py`** — Phase 1 only (turn decisions + accept/reject). Run one day and verify decisions parse correctly.
5. **`conversation.py`** — Add Phase 2 conversations. Run a day and read the transcripts.
6. **`task_experience.py`** — Add task experiences. Verify solo and shared tasks work.
7. **`gm.py`** — Unusual action resolution, nightly report, world state update.
8. **Evening reflections** — Phase 3. Verify journals get appended.
9. **Weekly maintenance** — Journal + world state compression.
10. **`main.py`** — Wire up day mode, week mode, --continue, --tier flags, terminal output.
11. **`viewer.py`** — Web viewer (build last — the simulation works without it).
12. **`batch_api.py`** — Optimize with batch API for cost savings (can be added after everything works synchronously).

**Note on Gemini model strings:** The exact API model identifiers may differ from the short names used in this doc (e.g., `gemini-2.5-flash` might need to be `gemini-2.5-flash-preview-04-17` or similar). Check the current Gemini API docs at https://ai.google.dev/gemini-api/docs/models for the exact strings when implementing. Similarly, verify Anthropic model strings at https://docs.anthropic.com/en/docs/about-claude/models.

---

## Cost Estimate (All WITH Batch 50% Discount)

### Budget: All Gemini

| Call type | Count | Model | Cost/day |
|---|---|---|---|
| All agent calls | ~42 | Flash ($0.075/$0.30) | $0.012 |
| All GM/parsing | ~22 | Flash-Lite ($0.05/$0.20) | $0.002 |
| **Daily** | | | **$0.014** |
| **Monthly** | | | **$0.41** |

### Standard: Hybrid Sonnet + Gemini

| Call type | Count | Model | Cost/day |
|---|---|---|---|
| Personality calls (conv, task, reflect) | ~31 | Sonnet ($1.50/$7.50) | $0.163 |
| Mechanical calls (decisions, approve) | ~11 | Flash ($0.075/$0.30) | $0.002 |
| GM/parsing calls | ~22 | Flash-Lite ($0.05/$0.20) | $0.002 |
| **Daily** | | | **$0.17** |
| **Monthly** | | | **$5.00** |

### Premium: All Claude

| Call type | Count | Model | Cost/day |
|---|---|---|---|
| All agent calls | ~42 | Sonnet ($1.50/$7.50) | $0.218 |
| All GM/parsing | ~22 | Haiku ($0.50/$2.50) | $0.028 |
| **Daily** | | | **$0.25** |
| **Monthly** | | | **$7.50** |

**With prompt caching (~20-30% additional savings):**
- Budget: ~$0.30/mo
- Standard: ~$4/mo
- Premium: ~$6/mo

---

## What to Observe

**Identity Formation** — Personality divergence? Self-concept accuracy? Identity crises?

**Social Dynamics** — Pair bonds? Rejections? Popular/isolated agents? Rivalries?

**The Village** — What's built/destroyed? Church claimed? Organized or chaotic?

**Emergent Culture** — Norms, rituals? Leaders? Art? Shared language?

**The Directive** — How does each interpret "live life to the fullest"?

**Task vs. Social** — Building preference vs talking? Different relationship quality?

**Unusual Behaviors** — Escape attempts? Deception? Organic justice?

**Tier Comparison** — If switching tiers, compare personality depth across same agents.

---

## Known Edge Cases

**Materials:** Grass, river stones, water, mud, wood from structures. No trees, no iron, no tools. GM presents constraints in task experiences.

**Discovery:** World state is source of truth. GM can introduce minor plausible finds (a flat stone, clay) but nothing game-breaking.

**Food/survival:** Not modeled. If agents notice, GM treats it as mystery.

**Physical harm:** Allowed. No rules. GM resolves with lasting consequences.

**The wall:** Truly impassable. The one hard constraint. Attempts always fail interestingly.

**Popular agents losing agency:** Intentional — mirrors real life.

**Large group speaking time:** Realistic — some stay quiet.

**Simultaneous task conflicts:** GM resolves independently, world state controller reconciles.

**Going meta:** Fine. Let it play out.

**Reading journals:** Journals are meta. GM resolves as observation/searching.

**7 is odd:** Guarantees solo agents most days. Feature, not bug.

**Journal vs. behavior divergence:** Most interesting thing to watch for.
