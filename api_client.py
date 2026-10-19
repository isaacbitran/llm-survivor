"""API client for Anthropic and Google Gemini with retry logic."""

import os
import time
from config import TIERS

# Lazy singleton clients
_anthropic_client = None
_gemini_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
    return _gemini_client


def _call_anthropic(model, system_prompt, user_prompt, max_tokens):
    client = _get_anthropic_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_gemini(model, system_prompt, user_prompt, max_tokens):
    client = _get_gemini_client()
    from google.genai import types
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text


def _call_llm(provider, model, system_prompt, user_prompt, max_tokens):
    """Call an LLM with retry logic (5 attempts, longer waits for rate limits)."""
    last_error = None
    for attempt in range(5):
        try:
            if provider == "anthropic":
                return _call_anthropic(model, system_prompt, user_prompt, max_tokens)
            elif provider == "gemini":
                return _call_gemini(model, system_prompt, user_prompt, max_tokens)
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as e:
            last_error = e
            err_str = str(e).lower()

            # Fatal errors — don't retry
            if any(msg in err_str for msg in ["credit balance", "invalid_api_key", "authentication"]):
                print(f"  [FATAL API error — not retrying] {e}")
                raise

            is_rate_limit = "429" in str(e) or "rate_limit" in err_str
            if is_rate_limit:
                wait = 15 * (attempt + 1)
                print(f"  [Rate limited, waiting {wait}s... attempt {attempt + 1}/5]")
            else:
                wait = 3 * (attempt + 1)
                print(f"  [API retry {attempt + 1}/5] {e}")
            if attempt < 4:
                time.sleep(wait)
    raise RuntimeError(f"API call failed after 5 attempts: {last_error}")


def call_personality(system_prompt, user_prompt, max_tokens, tier_config):
    """Call the personality model (Sonnet)."""
    return _call_llm(
        tier_config["personality_provider"],
        tier_config["personality_model"],
        system_prompt,
        user_prompt,
        max_tokens,
    )


def call_mechanical(system_prompt, user_prompt, max_tokens, tier_config):
    """Call the mechanical model (Flash) for content generation."""
    return _call_llm(
        tier_config["mechanical_provider"],
        tier_config["mechanical_model"],
        system_prompt,
        user_prompt,
        max_tokens,
    )


def call_gm(system_prompt, user_prompt, max_tokens, tier_config):
    """Call the GM model for summaries and management tasks."""
    return _call_llm(
        tier_config["gm_provider"],
        tier_config["gm_model"],
        system_prompt,
        user_prompt,
        max_tokens,
    )


def validate_api_keys(tier_config):
    """Check that required API keys are set for the given tier."""
    errors = []
    providers_needed = set()
    for key in ["personality_provider", "mechanical_provider", "gm_provider"]:
        providers_needed.add(tier_config[key])

    if "anthropic" in providers_needed and not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append("ANTHROPIC_API_KEY environment variable not set")
    if "gemini" in providers_needed and not os.environ.get("GEMINI_API_KEY"):
        errors.append("GEMINI_API_KEY environment variable not set")

    return errors
