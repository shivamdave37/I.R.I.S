TURN: reviewer
STAGE: 3
ROUND: 0
BUILDER NOTES: Added Gemini and Ollama chat behind ask_ai(), ten-message chat history, quota error messaging with optional configured fallback, key redaction in logs, and direct news routing for the top five headlines. Selected Gemini model gemini-3.5-flash-lite and Ollama model gemma3:1b. Mocked provider and RSS tests added.
UNSURE ABOUT: Real Gemini credentials/quota and live BBC RSS availability require a human check. Gemini free-tier data use is described in README.md; avoid sending sensitive chat text.
REVIEWER FIXED: None yet.
REVIEWER UNRESOLVED (needs builder or human): None yet.
NEEDS HUMAN TEST (mic, speakers, app paths, clipboard, GitHub login): With a valid private .env key, ask a simple question and confirm a reply; try an unknown question while AI_PROVIDER=ollama and the local model is running; try news/latest news with internet access. Do not share or commit the key. Earlier Stage 2 microphone, speaker, and app-path checks remain applicable.
