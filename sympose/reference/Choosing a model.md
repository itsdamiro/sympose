# Choosing a model

## Which model does Sympose use out of the box?

The default is `ollama_chat/gemma2:9b`, a local model run by Ollama. Ollama has to be running and the model pulled with `ollama pull gemma2:9b`.

## How do I switch to a different model?

Type `/model` in the chat to open a picker: Gemma2:9b (local, default), Claude Sonnet 5 (cloud), GPT-4o mini (cloud), Gemini Flash (cloud), Gemini Pro (cloud), and Claude Haiku 4.5, Llama 3.3 70B, Llama 3.1 8B and DeepSeek V4 Flash through OpenRouter (cloud). The pick is kept for that persona.

## Which model runs when there are several choices?

In order: your `/model` pick, then the `model` line in the persona's `persona.yaml`, then `chat_model` in `settings.json`, then the built-in default.

## Can I use any other model?

Yes. `chat_model` and a persona's `model` accept any model name litellm understands, such as another local Ollama model like `ollama_chat/qwen3:8b`.

## How do cloud models work?

Cloud models are opt-in and need the provider's API key in `.env`: `ANTHROPIC_API_KEY` for Claude, `OPENAI_API_KEY` for GPT, `GEMINI_API_KEY` for Gemini and `OPENROUTER_API_KEY` for the OpenRouter ones.

## Can I use my Claude subscription, such as Pro or Max, for Claude in Sympose?

No. A subscription covers the Claude apps and Claude Code, and Anthropic's terms do not let another app sign in with it. Claude in Sympose runs on an API key from the Anthropic Console, put in `.env` as `ANTHROPIC_API_KEY`, billed apart from the subscription. Max and Team plans include a monthly API credit you can link to a Console organization; on other plans you pay from that account's balance.

## How much does Claude cost?

Claude is billed per use, by Anthropic, to the Console account the key belongs to. A normal chat turn costs a fraction of a cent, and a persona's unattended job costs more because it makes several calls. Sympose never turns on auto-reload or buys credit for you: leave auto-reload off in the Console, and what you put in is the most you can spend.

## What does a cloud model receive?

Your messages and the conversation are sent to that provider. Your notes, their properties and your recaps are sent only if you allow them: Sympose asks when you switch from a local model to a cloud one, and /share changes it later.

## Can I use another OpenRouter model?

Yes. Name it in `chat_model` or a persona's `model`, for example `openrouter/mistralai/mistral-large-2512`.

## Why do some features not work with my local model?

Some features need a model that can call tools, which means asking Sympose to do something mid-answer, such as opening a note. The default local model, gemma2:9b, cannot. Sympose then keeps its automatic search and Samantha works as before. Everything else works on any model.

## Which features need a model that can call tools?

Looking in your notes herself, `vault_lookup` `"ask"`, or by default on a tested model such as Gemini Flash: she searches, opens one, lists a folder or filters by tag and property, so you can ask for "the 5th note in my Movies folder". Making a new persona from a card in the web app needs one too. Remembering, recaps, condensing a long chat and searching by meaning work on every model.

## Which models can call tools?

Gemini Flash can, and most cloud models can, Claude Sonnet 5 among them. Of local models, Sympose asks Ollama: qwen3:8b and gemma4 can, gemma2:9b cannot. Those that can are often thinking models, which are slow on a laptop, so a cloud model is the smoother choice for `"ask"`.

## What can a local model not do as well as a cloud one?

A local model has a smaller window, so it holds less of a long chat and fewer notes at once, and it follows long lists and instructions less reliably. Sympose works around this: a map of your vault is always given, long chats are condensed, and notes are found for it.

## Why is a thinking model so slow?

A local reasoning model such as qwen3:8b spends a long time thinking before it answers. The extra search for follow-up questions is skipped for a model that cannot do it in time.
