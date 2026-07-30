# Reel — YouTube Video Q&A frontend

A lightweight Django frontend for a LangChain-powered YouTube video
summarizer + Q&A agent. Paste a link, get a summary, then ask questions
about the video in a chat panel.

No database is required — chat/video state lives in a signed session
cookie, so there's nothing to migrate before you run it.

## Project layout

```
yt_summarizer/
  pyproject.toml          # uv-managed deps
  manage.py
  config/                 # Django settings/urls
  chatapp/
    agents.py              # <-- THE ONLY FILE YOU EDIT to wire in LangChain
    views.py                # calls agents.load_video() / agents.ask_question()
    urls.py
    templates/chatapp/index.html
    static/chatapp/css/style.css
    static/chatapp/js/main.js
```

## Run it

```bash
cd yt_summarizer
uv sync
uv run manage.py runserver
```

Then open http://127.0.0.1:8000/

## Wiring in your LangChain agent(s)

Open `chatapp/agents.py`. It has exactly two functions the rest of the app
calls:

- `load_video(video_url) -> VideoContext` — runs when the user submits a
  link. Load the transcript (e.g. `YoutubeLoader`, `youtube-transcript-api`)
  and summarize it here. Return a `VideoContext(video_id, title, summary)`.
- `ask_question(video_context, question, history) -> str` — runs on every
  chat message. Build your retrieval/QA chain here and return the answer
  string. `history` gives you prior turns for conversational memory.

Add your real dependencies to `pyproject.toml` (a few common ones are
commented out already) and run `uv sync` again:

```toml
dependencies = [
    "django>=5.0,<6.0",
    "langchain",
    "langchain-openai",
    "langchain-community",
    "youtube-transcript-api",
]
```

If your pipeline needs to cache something heavy per video (a vectorstore,
a retriever, an LLM client), don't put it in the return value of
`load_video` — session storage is a signed cookie, so it only holds plain
JSON. Instead keep it in the in-memory `_VIDEO_CACHE` dict already stubbed
in `agents.py`, keyed by `video_id`.

Everything else — the Django views, templates, CSS, JS — is done and
shouldn't need to change as you iterate on your chains.

## Adding more agents

Want a second capability (e.g. "generate quiz questions", "translate
summary")? Add another function to `agents.py`, a matching view in
`views.py` + URL in `urls.py`, and a small fetch call in `main.js`. The
existing `load_video` / `ask_question` pair is the template to copy.
