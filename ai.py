"""AI chat through the configured Gemini or Ollama provider."""

import os

import requests
from dotenv import load_dotenv
from google import genai

import config


SYSTEM_PROMPT = "You are a helpful, concise assistant. Reply in 2 to 3 sentences unless asked for detail."
CHAT_HISTORY = []


def ask_ai(messages):
    """Answer the latest user text and keep only the last ten chat messages."""
    global CHAT_HISTORY

    if isinstance(messages, str):
        user_text = messages.strip()
    elif isinstance(messages, list):
        user_text = ""
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                user_text = str(message.get("content", "")).strip()
                break
    else:
        user_text = ""

    if not user_text:
        return "I didn't receive a message to send to the AI."

    # Refuse to transmit the configured key if it was pasted into the chat by mistake.
    load_dotenv()
    configured_key = os.getenv("GEMINI_API_KEY")
    if configured_key and configured_key in user_text:
        return "I can't send a message containing the configured Gemini API key."

    CHAT_HISTORY.append({"role": "user", "content": user_text})
    CHAT_HISTORY = CHAT_HISTORY[-10:]
    providers = [str(config.AI_PROVIDER).strip().lower()]
    fallback_provider = config.AI_FALLBACK_PROVIDER
    if fallback_provider and str(fallback_provider).strip().lower() not in providers:
        providers.append(str(fallback_provider).strip().lower())

    first_rate_error = ""
    for provider in providers:
        try:
            if provider == "gemini":
                # Load only the API key variable; never read or send the .env file itself.
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    return "Gemini is selected, but GEMINI_API_KEY is missing from .env."

                conversation = [SYSTEM_PROMPT, "Conversation so far:"]
                for message in CHAT_HISTORY:
                    speaker = "You" if message["role"] == "user" else "Jarvis"
                    conversation.append(f"{speaker}: {message['content']}")
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents="\n".join(conversation),
                )
                reply = (response.text or "").strip()
            elif provider == "ollama":
                ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + CHAT_HISTORY
                response = requests.post(
                    config.OLLAMA_URL,
                    json={"model": config.OLLAMA_MODEL, "messages": ollama_messages, "stream": False},
                    timeout=30,
                )
                response.raise_for_status()
                reply = response.json().get("message", {}).get("content", "").strip()
            else:
                return f"Unknown AI provider '{provider}'. Choose gemini or ollama in config.py."

            if not reply:
                raise ValueError("The AI provider returned an empty response.")
            CHAT_HISTORY.append({"role": "assistant", "content": reply})
            CHAT_HISTORY = CHAT_HISTORY[-10:]
            return reply
        except Exception as error:
            error_text = str(error)
            lower_error = error_text.lower()
            is_quota_error = any(
                phrase in lower_error
                for phrase in ("429", "quota", "rate limit", "resource exhausted", "too many requests")
            )
            if is_quota_error and provider != providers[-1]:
                first_rate_error = f"{provider.title()} reached a rate or quota limit."
                continue
            if is_quota_error:
                return f"{provider.title()} reached its free-tier rate or quota limit. Please wait and try again."
            if first_rate_error:
                # Avoid echoing raw provider errors because they may contain sensitive request details.
                return f"{first_rate_error} The configured fallback provider could not respond."
            if provider == "ollama":
                return "I couldn't reach Ollama. Check that Ollama is running and the configured model is installed."
            return "I couldn't get an AI response. Check your internet connection and Gemini API key."

    return "I couldn't get an AI response right now."
