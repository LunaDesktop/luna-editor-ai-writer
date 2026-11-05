#!/usr/bin/env python3
"""AI Writer — wtyczka do Luna Editor.

Czyta kontekst ze standardowego wejścia i zmienne środowiskowe ustawione przez
edytor (LUNA_PLUGIN_* oraz LUNA_SETTING_*), wysyła zapytanie do wybranego
dostawcy LLM i wypisuje gotowy tekst na standardowe wyjście.

Nie wymaga żadnych bibliotek zewnętrznych — tylko biblioteki standardowe Pythona.
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
        with urllib.request.urlopen(request, timeout=120) as response:
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


def openai_compatible(url, key, model, user, provider):
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    data = request_json(url, payload, headers, provider)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        fail(f"{provider}: nieoczekiwana odpowiedź API")


def ask_gemini(key, model, user):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.7},
    }
    data = request_json(url, payload, {"Content-Type": "application/json"}, "gemini")
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError):
        fail("gemini: nieoczekiwana odpowiedź API")


def ask_anthropic(key, model, user):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.7,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user}],
    }
    data = request_json(url, payload, headers, "anthropic")
    try:
        return "".join(block.get("text", "") for block in data["content"])
    except (KeyError, TypeError):
        fail("anthropic: nieoczekiwana odpowiedź API")


def ask_ollama(model, user):
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    data = request_json(url, payload, {"Content-Type": "application/json"}, "ollama")
    try:
        return data["message"]["content"]
    except (KeyError, TypeError):
        fail("ollama: nieoczekiwana odpowiedź API")


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

    instruction = setting("LUNA_PLUGIN_INSTRUCTION")
    model = setting("LUNA_SETTING_MODEL") or DEFAULT_MODELS.get(provider, "")
    if not model:
        model = DEFAULT_MODELS[provider]

    user = build_prompt(action, instruction, read_context(), language)

    if provider == "gemini":
        result = ask_gemini(key, model, user)
    elif provider == "anthropic":
        result = ask_anthropic(key, model, user)
    elif provider == "ollama":
        result = ask_ollama(model, user)
    elif provider == "openai":
        result = openai_compatible(
            "https://api.openai.com/v1/chat/completions", key, model, user, provider
        )
    elif provider == "deepseek":
        result = openai_compatible(
            "https://api.deepseek.com/chat/completions", key, model, user, provider
        )
    elif provider == "openrouter":
        result = openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            key,
            model,
            user,
            provider,
        )
    elif provider == "mistral":
        result = openai_compatible(
            "https://api.mistral.ai/v1/chat/completions", key, model, user, provider
        )
    elif provider == "groq":
        result = openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions", key, model, user, provider
        )
    else:  # pragma: no cover — lista jest zamknięta wyżej
        fail(f"Nieznany dostawca LLM: {provider}")

    text = clean(result)
    if not text:
        fail("Model nie zwrócił tekstu.")
    print(text)


if __name__ == "__main__":
    main()
