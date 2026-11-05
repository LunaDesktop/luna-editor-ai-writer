#!/usr/bin/env python3
"""AI Writer — wtyczka do Luna Editor.

Dwa tryby pracy:

* polecenia jednorazowe (``ask``, ``write``, ``continue``, ``edit``,
  ``translate``, ``summary``) — wynik trafia do edytora jako tekst,
* ``__chat__`` — agent w panelu czatu: dostaje JSON z historią rozmowy,
  listą plików projektu i treścią aktywnego pliku, a odpowiada JSON-em
  ``{"text": "...", "tool_calls": [...]}``. Edytor wykonuje narzędzia
  (``read_file``, ``list_dir``, ``search``, ``write_file``, ``create_file``,
  ``delete_file``) i wywołuje wtyczkę ponownie.

Nie wymaga żadnych bibliotek zewnętrznych — tylko biblioteki standardowe.
"""

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "deepseek": "deepseek-chat",
    "openrouter": "openai/gpt-4o-mini",
    "mistral": "mistral-large-latest",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.2",
}

# Etykiety z manifestu → identyfikatory używane w kodzie.
PROVIDERS = {
    "gemini": "gemini",
    "chatgpt (openai)": "openai",
    "openai": "openai",
    "claude (anthropic)": "anthropic",
    "anthropic": "anthropic",
    "deepseek": "deepseek",
    "openrouter": "openrouter",
    "mistral": "mistral",
    "groq": "groq",
    "ollama": "ollama",
}

SYSTEM_PROMPT = (
    "Jesteś asystentem pisarskim w edytorze tekstu Luna. "
    "Odpowiadaj w języku tekstu lub instrukcji użytkownika. "
    "Zwracaj wyłącznie gotową treść do wstawienia: bez komentarzy, "
    "bez bloków kodu, bez cudzysłowów otaczających całość."
)

AGENT_SYSTEM = (
    "Jesteś agentem programistycznym wbudowanym w edytor Luna. "
    "Pracujesz na prawdziwym projekcie i masz narzędzia do czytania, "
    "przeszukiwania i zapisywania plików. "
    "Odpowiadaj ZAWSZE jednym obiektem JSON, bez markdown i bez komentarzy:\n"
    '{"text": "<krótkie wyjaśnienie po polsku>", '
    '"tool_calls": [{"tool": "read_file", "path": "src/main.rs"}]}\n'
    "Narzędzia: read_file(path), list_dir(path), search(query, path), "
    "write_file(path, content), create_file(path, content), delete_file(path).\n"
    "Zasady: ścieżki są zawsze względne wobec katalogu projektu; "
    "write_file wymaga PEŁNEJ, gotowej treści pliku; "
    "nie wymyślaj zawartości plików — najpierw je przeczytaj; "
    "gdy zadanie jest wykonane, zwróć sam {\"text\": \"...\"} bez tool_calls."
)


def setting(name, default=""):
    return os.environ.get(name, default).strip()


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def read_context():
    return sys.stdin.read()


def request_json(url, payload, headers, provider):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:600]
        fail(f"{provider}: HTTP {error.code}: {detail}")
    except Exception as error:  # noqa: BLE001 — komunikat ma trafić do edytora
        fail(f"{provider}: {error}")


def request_get(url, headers, provider):
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:600]
        fail(f"{provider}: HTTP {error.code}: {detail}")
    except Exception as error:  # noqa: BLE001
        fail(f"{provider}: {error}")


def list_models(provider, key):
    """Zwraca listę identyfikatorów modeli dostępnych dla klucza."""
    if provider == "ollama":
        data = request_get("http://localhost:11434/api/tags", {}, provider)
        return [model.get("name", "") for model in data.get("models", [])]

    if provider == "gemini":
        data = request_get(
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"?key={key}",
            {},
            provider,
        )
        return [
            model.get("name", "").removeprefix("models/")
            for model in data.get("models", [])
            if "generateContent" in model.get("supportedGenerationMethods", [])
        ]

    if provider == "anthropic":
        data = request_get(
            "https://api.anthropic.com/v1/models",
            {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            provider,
        )
        return [model.get("id", "") for model in data.get("data", [])]

    endpoints = {
        "openai": "https://api.openai.com/v1/models",
        "deepseek": "https://api.deepseek.com/models",
        "openrouter": "https://openrouter.ai/api/v1/models",
        "mistral": "https://api.mistral.ai/v1/models",
        "groq": "https://api.groq.com/openai/v1/models",
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = request_get(endpoints[provider], headers, provider)
    models = [model.get("id", "") for model in data.get("data", [])]
    if provider == "openai":
        prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt")
        models = [model for model in models if model.startswith(prefixes)]
    return models


def openai_compatible(url, key, model, user, provider, system=SYSTEM_PROMPT):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://luna.paganlinux.eu"
        headers["X-Title"] = "Luna Editor"
    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    data = request_json(url, payload, headers, provider)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        fail(f"{provider}: nieoczekiwana odpowiedź API")


def ask_gemini(key, model, user, system=SYSTEM_PROMPT):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.7},
    }
    data = request_json(url, payload, {"Content-Type": "application/json"}, "gemini")
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError):
        fail("gemini: nieoczekiwana odpowiedź API")


def ask_anthropic(key, model, user, system=SYSTEM_PROMPT):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": 8192,
        "temperature": 0.7,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    data = request_json(url, payload, headers, "anthropic")
    try:
        return "".join(block.get("text", "") for block in data["content"])
    except (KeyError, TypeError):
        fail("anthropic: nieoczekiwana odpowiedź API")


def ask_ollama(model, user, system=SYSTEM_PROMPT):
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    data = request_json(url, payload, {"Content-Type": "application/json"}, "ollama")
    try:
        return data["message"]["content"]
    except (KeyError, TypeError):
        fail("ollama: nieoczekiwana odpowiedź API")


def ask(provider, key, model, user, system=SYSTEM_PROMPT):
    if provider == "gemini":
        return ask_gemini(key, model, user, system)
    if provider == "anthropic":
        return ask_anthropic(key, model, user, system)
    if provider == "ollama":
        return ask_ollama(model, user, system)
    endpoints = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/chat/completions",
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        "mistral": "https://api.mistral.ai/v1/chat/completions",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
    }
    return openai_compatible(endpoints[provider], key, model, user, provider, system)


def build_prompt(action, instruction, payload, language):
    payload = payload.strip()
    if len(payload) > 12000:
        if action == "continue":
            payload = "…\n" + payload[-12000:]
        else:
            payload = payload[:12000] + "\n…"

    if action == "ask":
        if not instruction:
            fail("Wpisz pytanie albo polecenie dla modelu.")
        return (
            "Odpowiedz na poniższe pytanie/polecenie użytkownika "
            f"(język: {language}). Zwróć tylko odpowiedź, bez komentarzy:\n"
            f"{instruction}\n\nKontekst dokumentu:\n---\n{payload}\n---"
        )
    if action == "write":
        if not instruction:
            fail("Napisz, co mam wygenerować (pole instrukcji jest puste).")
        return (
            f"Napisz treść zgodnie z instrukcją:\n{instruction}\n\n"
            f"Kontekst dokumentu (język: {language}):\n---\n{payload}\n---"
        )
    if action == "continue":
        return (
            "Kontynuuj poniższy tekst w tym samym stylu i tonie. "
            "Zwróć tylko dalszy ciąg, bez powtarzania istniejącego tekstu:\n"
            f"---\n{payload}\n---"
        )
    if action == "edit":
        return (
            "Popraw gramatykę, interpunkcję i styl poniższego tekstu, "
            "zachowując jego sens i język. Zwróć wyłącznie poprawioną wersję:\n"
            f"---\n{payload}\n---"
        )
    if action == "translate":
        target = instruction or "na język angielski"
        return (
            f"Przetłumacz poniższy tekst {target}. "
            "Zachowaj formatowanie i zwróć wyłącznie tłumaczenie:\n"
            f"---\n{payload}\n---"
        )
    if action == "summary":
        return (
            "Streść poniższy tekst zwięźle, zachowując najważniejsze fakty. "
            f"Język: {language}.\n---\n{payload}\n---"
        )
    fail(f"Nieznane polecenie wtyczki: {action}")


def build_agent_prompt(payload):
    """Składa prompt agenta z JSON-a wysłanego przez edytor."""
    try:
        data = json.loads(payload) if payload.strip() else {}
    except json.JSONDecodeError as error:
        fail(f"Niepoprawny JSON od edytora: {error}")

    workspace = data.get("workspace") or {}
    files = workspace.get("files") or []
    contents = workspace.get("contents") or []
    messages = data.get("messages") or []
    tools = data.get("tools") or []

    lines = [
        f"Projekt: {workspace.get('name', '')} (katalog: {workspace.get('root', '')})",
        "",
        "Pliki projektu (ścieżka, rozmiar):",
    ]
    for item in files[:400]:
        lines.append(f"- {item.get('path')} ({item.get('size')} B)")

    if contents:
        lines.append("")
        lines.append("Treść plików (może być obcięta):")
        for item in contents:
            lines.append(f"--- {item.get('path')} ---")
            lines.append(str(item.get("text", "")))

    active = data.get("file")
    if active:
        lines.append("")
        lines.append(
            f"Aktywny plik w edytorze: {active.get('path')} "
            f"(język: {active.get('language')})"
        )
        selection = active.get("selection") or ""
        if selection.strip():
            lines.append("Zaznaczony fragment:")
            lines.append(selection)

    lines.append("")
    lines.append("Rozmowa (od najstarszej wiadomości):")
    for message in messages:
        role = message.get("role", "user")
        lines.append(f"[{role}] {message.get('content', '')}")

    lines.append("")
    lines.append(f"Dostępne narzędzia: {', '.join(tools)}")
    lines.append("Odpowiedz teraz wyłącznie obiektem JSON zgodnie z formatem.")
    return "\n".join(lines)


def extract_json(text):
    """Wyciąga pierwszy zbalansowany obiekt JSON z odpowiedzi modelu."""
    text = text.strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    if text.startswith("{"):
        candidate = text
    else:
        start = text.find("{")
        if start < 0:
            return None
        candidate = text[start:]
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(candidate):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return candidate[: index + 1]
    return None


def emit_agent_reply(raw):
    """Normalizuje odpowiedź modelu do formatu, który rozumie edytor."""
    text = (raw or "").strip()
    candidate = extract_json(text)
    data = None
    if candidate:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        print(json.dumps({"text": text}, ensure_ascii=False))
        return

    reply = {"text": str(data.get("text") or data.get("message") or "").strip()}
    calls = data.get("tool_calls") or data.get("tools") or data.get("actions") or []
    cleaned = []
    for call in calls:
        if isinstance(call, str):
            cleaned.append({"tool": call})
            continue
        if not isinstance(call, dict):
            continue
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        tool = call.get("tool") or call.get("name") or call.get("action")
        if not tool:
            continue
        entry = {"tool": str(tool)}
        for key in ("path", "content", "query"):
            value = args.get(key, call.get(key))
            if value is not None:
                entry[key] = str(value)
        cleaned.append(entry)
    if cleaned:
        reply["tool_calls"] = cleaned
    print(json.dumps(reply, ensure_ascii=False))


def clean(text):
    text = (text or "").strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1])
    return text.strip()


def main():
    action = setting("LUNA_PLUGIN_ACTION")
    language = setting("LUNA_PLUGIN_LANGUAGE", "text")
    provider = setting("LUNA_SETTING_PROVIDER", "Gemini").lower()
    provider = PROVIDERS.get(provider, provider)
    key = setting("LUNA_SETTING_API_KEY")

    if provider not in DEFAULT_MODELS:
        fail(f"Nieznany dostawca LLM: {provider}")
    if provider != "ollama" and not key:
        fail(
            "Brak klucza API. Otwórz Plugins → AI Writer → Settings "
            "i wpisz klucz wybranego dostawcy."
        )

    if action == "__list_models__":
        models = [model for model in list_models(provider, key) if model]
        if not models:
            fail("Dostawca nie zwrócił listy modeli.")
        for model in sorted(set(models), key=str.lower):
            print(model)
        return

    model = setting("LUNA_SETTING_MODEL") or DEFAULT_MODELS.get(provider, "")
    if not model:
        model = DEFAULT_MODELS[provider]

    if action == "__chat__":
        prompt = build_agent_prompt(read_context())
        result = ask(provider, key, model, prompt, AGENT_SYSTEM)
        emit_agent_reply(result)
        return

    instruction = setting("LUNA_PLUGIN_INSTRUCTION")
    user = build_prompt(action, instruction, read_context(), language)
    result = ask(provider, key, model, user)

    text = clean(result)
    if not text:
        fail("Model nie zwrócił tekstu.")
    print(text)


if __name__ == "__main__":
    main()
