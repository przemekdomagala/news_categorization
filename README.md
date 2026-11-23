# Pobieranie artykułów z FreeNewsAPI

Skrypty pobierają angielskie artykuły z [FreeNewsAPI](https://www.freenewsapi.io/) z podziałem na topic.
Dane służą do projektu data mining: na podstawie treści artykułu przewidujemy jego topic.

## Wymagania

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (sam pobierze Pythona 3.14 i zależności)
- własny klucz API z freenewsapi.io

## Instalacja

W katalogu projektu:

```bash
uv sync
```

Utwórz plik `.env` obok skryptów:

```
API_KEY=twoj_klucz
```

Nie wysyłaj nikomu pliku `.env` i nie wrzucaj go do repozytorium.

## Pobieranie

```bash
uv run python download_news.py --target 12000
```

`--target` to docelowa liczba artykułów z treścią (domyślnie 12000).

Dłuższe pobieranie w tle:

```bash
# macOS (caffeinate blocks sleep, but not when the lid is closed)
nohup caffeinate -i uv run python -u download_news.py --target 12000 >> download.log 2>&1 &

# Linux
nohup uv run python -u download_news.py --target 12000 >> download.log 2>&1 &
```

Na Windowsie uruchom zwykłe polecenie w osobnym oknie terminala i wyłącz usypianie komputera.

Postęp na macOS i Linuksie:

```bash
tail -f download.log
```

Zatrzymanie na macOS i Linuksie:

```bash
pkill -f download_news.py
```

W terminalu na pierwszym planie wystarczy `Ctrl+C`.

## Ile to trwa

API pozwala na 2 zapytania na sekundę i 5000 zapytań dziennie. `/news` zwraca tylko tytuły,
więc treść każdego artykułu to osobne zapytanie do `/details`.

- 5000 zapytań to około 50 minut pracy i około 4500 artykułów.
- 12 000 artykułów od zera wymaga około 13 000 zapytań, czyli trzech dziennych limitów.

Po wyczerpaniu limitu skrypt sam czeka na reset, więc komputer musi w tym czasie być włączony.
Zgodnie z regulaminem API nie obchodź limitu dodatkowymi kontami ani kluczami.

## Przerywanie i wznawianie

Postęp jest zapisywany na bieżąco w `data/news.sqlite`. Po ponownym uruchomieniu skrypt idzie dalej
od miejsca, w którym skończył, także z wyższym `--target`.

- Nie usuwaj `data/news.sqlite`, bo pobieranie zacznie się od zera.
- Nie uruchamiaj dwóch kopii skryptu naraz.
- Nie przenoś ani nie zmieniaj nazwy katalogu projektu w trakcie działania skryptu, także podczas oczekiwania na reset limitu. Najpierw go zatrzymaj.

## Eksport danych

```bash
uv run python export_dataset.py
```

Eksport można uruchomić także w trakcie pobierania. Trzeba go powtórzyć, aby objął nowe artykuły.

| Plik | Zawartość |
|---|---|
| `data/articles.csv` | wszystkie artykuły, topiki rozdzielone znakiem `\|` |
| `data/by_topic/<topic>.jsonl` | artykuły danego topicu |

Eksport pomija treści krótsze niż 200 znaków i duplikaty treści.
Artykuł może mieć kilka topiców, więc może występować w kilku plikach `by_topic`.

## Regulamin

Regulamin API dopuszcza użycie badawcze i akademickie, ale zakazuje republikowania pełnych artykułów.
Nie publikuj pobranego zbioru, np. w publicznym repozytorium.
