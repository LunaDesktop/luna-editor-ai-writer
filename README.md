# AI Writer — wtyczka do Luna Editor

Agent AI dla Edytora Luny: pisze nowe treści, kontynuuje dokument, poprawia
i streszcza zaznaczenie oraz tłumaczy tekst. Obsługuje Gemini, OpenAI
(ChatGPT), Anthropic (Claude), DeepSeek, OpenRouter, Mistral, Groq oraz lokalny
Ollama.

## Instalacja

W Edytorze: **menu ☰ → Plugins… → wklej adres repozytorium → Install**.

```
https://github.com/LunaDesktop/luna-editor-ai-writer
```

Potrzebne są: `python3` oraz `curl` (albo `wget`) i `tar` — instalator pobiera
archiwum z GitHuba.

## Konfiguracja

**Plugins… → AI Writer → Settings**:

| Pole | Opis |
|---|---|
| Dostawca LLM | `Gemini`, `ChatGPT (OpenAI)`, `Claude (Anthropic)`, `DeepSeek`, `OpenRouter`, `Mistral`, `Groq`, `Ollama` |
| Model | np. `gemini-2.0-flash`, `gpt-4o-mini`, `claude-3-5-sonnet-latest`, `deepseek-chat` |
| Klucz API | klucz wybranego dostawcy (dla `Ollama` nie jest wymagany) |

Klucz jest zapisywany **lokalnie** w
`~/.config/luna/editor/plugins/ai-writer.conf` z prawami `0600` i wysyłany
wyłącznie do wybranego dostawcy API. Wtyczka nie zbiera żadnych danych.

Domyślne modele:

| Dostawca | Model domyślny |
|---|---|
| Gemini | `gemini-2.0-flash` |
| OpenAI | `gpt-4o-mini` |
| Anthropic | `claude-3-5-sonnet-latest` |
| DeepSeek | `deepseek-chat` |
| OpenRouter | `openai/gpt-4o-mini` |
| Mistral | `mistral-large-latest` |
| Groq | `llama-3.3-70b-versatile` |
| Ollama | `llama3.2` (lokalnie, `http://localhost:11434`) |

## Polecenia

| Polecenie | Kontekst | Wynik |
|---|---|---|
| **Napisz tekst…** | cały dokument | wstawia wygenerowaną treść w miejscu kursora |
| **Kontynuuj pisanie** | cały dokument | dopisuje dalszy ciąg w miejscu kursora |
| **Popraw zaznaczenie** | zaznaczenie | zamienia zaznaczenie poprawioną wersją |
| **Przetłumacz zaznaczenie…** | zaznaczenie | zamienia zaznaczenie tłumaczeniem |
| **Streść zaznaczenie** | zaznaczenie | wstawia streszczenie |

## Jak to działa

Wtyczka jest zwykłym programem. Edytor przekazuje jej:

- `LUNA_PLUGIN_ACTION` — identyfikator polecenia (`write`, `continue`, …),
- `LUNA_PLUGIN_INSTRUCTION` — tekst wpisany w oknie polecenia (jeśli jest),
- `LUNA_PLUGIN_PATH`, `LUNA_PLUGIN_LANGUAGE` — ścieżka i język dokumentu,
- `LUNA_SETTING_PROVIDER`, `LUNA_SETTING_MODEL`, `LUNA_SETTING_API_KEY` —
  ustawienia z manifestu i pliku konfiguracji,
- treść kontekstu na standardowym wejściu.

Wynik (czysty tekst) trafia na standardowe wyjście. Błędy wypisuje na
standardowe wyjście błędów — Edytor pokazuje je w oknie alertu.

## Licencja

GPL-3.0-or-later. © 2026 Luna Project.
