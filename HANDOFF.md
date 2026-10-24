TURN: human
STAGE: 3
ROUND: 0
BUILDER NOTES: Added Gemini and Ollama chat behind ask_ai(), ten-message chat history, quota error messaging with optional configured fallback, key redaction in logs, and direct news routing for the top five headlines. Selected Gemini model gemini-3.5-flash-lite and Ollama model gemma3:1b. Mocked provider and RSS tests added.
UNSURE ABOUT: Real Gemini credentials/quota and live BBC RSS availability require a human check. Gemini free-tier data use is described in README.md; avoid sending sensitive chat text.
REVIEWER FIXED: Rolled back unfulfilled user messages from CHAT_HISTORY when an AI call fails so conversation history is not corrupted; added check for placeholder template API keys in .env; decoded HTML entities in news titles with html.unescape; routed conversational news queries ("whats the news", "tell me the news") directly to news skill; safeguarded key redaction in log_action against blank keys; expanded test coverage from 38 to 42 unit tests.
REVIEWER UNRESOLVED (needs builder or human): None
NEEDS HUMAN TEST (mic, speakers, app paths, clipboard, GitHub login): Paste real GEMINI_API_KEY into .env and ask a question (e.g. "who invented the telephone"); test rate-limit/fallback behavior if Ollama is running locally; test live "latest news" and "tell me the news" with internet connection; verify unplugged internet produces clean error message. Do not share or commit .env.
