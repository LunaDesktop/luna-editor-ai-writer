# AI Writer — wtyczka do Luna Editor

Agent AI dla Edytora Luny: pisze nowe treści, kontynuuje dokument, poprawia
i streszcza zaznaczenie oraz tłumaczy tekst. Ma też **panel czatu z agentem**,
który widzi projekt i potrafi czytać oraz zapisywać pliki. Obsługuje Gemini,
OpenAI (ChatGPT), Anthropic (Claude), DeepSeek, OpenRouter, Mistral, Groq oraz
lokalny Ollama.

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
| Model | **lista pobierana z API** po kliknięciu — wybór z popupu z wyszukiwaniem |
| Klucz API | klucz wybranego dostawcy (dla `Ollama` nie jest wymagany) |

Po wpisaniu klucza kliknij pole **Model** — wtyczka pobierze listę modeli
dostępnych dla tego klucza i pokaże ją w wyszukiwanym popupie. Lista jest
odświeżana po zmianie klucza lub dostawcy.

Domyślne modele (gdy dostawca nie zwróci listy):

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

Po instalacji polecenia są dostępne w **menu głównym Edytora** (sekcja
„AI Writer”) oraz w menedżerze **Plugins…**.

| Polecenie | Kontekst | Wynik |
|---|---|---|
| **Zapytaj AI…** | cały dokument | odpowiada na wpisane pytanie/polecenie w miejscu kursora |
| **Napisz tekst…** | cały dokument | wstawia wygenerowaną treść w miejscu kursora |
| **Kontynuuj pisanie** | cały dokument | dopisuje dalszy ciąg w miejscu kursora |
| **Popraw zaznaczenie** | zaznaczenie | zamienia zaznaczenie poprawioną wersją |
| **Przetłumacz zaznaczenie…** | zaznaczenie | zamienia zaznaczenie tłumaczeniem |
| **Streść zaznaczenie** | zaznaczenie | wstawia streszczenie |

## Czat z agentem

Wtyczka deklaruje `chat = true`, więc w Edytorze pojawia się **panel czatu**
(ikona czatu w nagłówku, `Ctrl+Shift+A`). To tryb agenta: model widzi strukturę
projektu, treść małych plików i aktywny dokument, a w rozmowie może używać
narzędzi:

| Narzędzie | Do czego |
|---|---|
| `read_file` | przeczytanie pliku |
| `list_dir` | lista zawartości katalogu |
| `search` | szukanie tekstu w projekcie |
| `write_file` | zapis całego pliku |
| `create_file` | nowy plik (błąd, gdy istnieje) |
| `delete_file` | usunięcie pliku |

Edytor wykonuje narzędzia i wraca do modelu z wynikami (do 6 kroków na turę),
więc zadania typu „dodaj testy do `src/main.rs`” albo „popraw literówki w
README” dzieją się na prawdziwych plikach. Zapis do pliku z niezapisanymi
zmianami jest odrzucany, a wszystkie ścieżki muszą mieścić się w katalogu
projektu.

Model jest proszony o odpowiedź w JSON-ie (`{"text": …, "tool_calls": […]}`),
ale zwykła odpowiedź tekstowa też działa — wtedy kończy turę.

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
