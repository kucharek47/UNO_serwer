# UNO Serwer

Serwer backendowy dla gry w UNO, napisany w języku Python z wykorzystaniem bibliotek Flask oraz Flask-SocketIO. Aplikacja zarządza logiką gry, pokojami, graczami (w tym botami) oraz komunikacją w czasie rzeczywistym poprzez WebSockets. Projekt jest połączony z bazą danych PostgreSQL i serwuje aplikację kliencką.

🌐 **Wersja Live (Demo):** [uno.kucharek47.pl](https://uno.kucharek47.pl)  
🎨 **Kod źródłowy frontendu:** [github.com/kucharek47/UNOFront](https://github.com/kucharek47/UNOFront)  

## Struktura projektu

- `app.py` - główny plik aplikacji Flask, obsługujący routing, serwowanie plików statycznych i zdarzenia Socket.IO.
- `logika_serwerowa.py` / `gra_w_uno.py` - pliki zawierające mechanikę, środowisko gry UNO oraz logikę sztucznej inteligencji / botów.
- `bazy.py` - moduł odpowiadający za połączenie z bazą danych i zapytania (tworzenie pokoi, zarządzanie stanem gry).
- `dist/UNOFront/browser/` - katalog zawiera gotowy, skompilowany frontend w Angularze v21 (wynik polecenia `ng build` z repozytorium frontendu). Pliki te są domyślnie serwowane przez główny endpoint serwera Flask.
- `docker-compose.yml` i `Dockerfile` - pliki konfiguracyjne do szybkiego wdrożenia aplikacji za pomocą Dockera.

## Wymagania

- Docker
- Docker Compose

## Instalacja i uruchomienie (Docker)

1. Sklonuj repozytorium:
```bash
git clone <adres_repozytorium>
cd uno_serwer
```

2. Skonfiguruj zmienne środowiskowe:
Utwórz plik `.env` w głównym katalogu projektu i uzupełnij go podstawowymi danymi dla bazy danych oraz serwera, np.:
```env
FLASK_SECRET_KEY=twoj_bardzo_tajny_klucz
POSTGRES_USER=twoj_uzytkownik
POSTGRES_PASSWORD=twoje_haslo
POSTGRES_DB=nazwa_bazy_danych
```

3. Uruchom kontenery:
Zbuduj i uruchom aplikację wraz z bazą danych PostgreSQL, korzystając z Docker Compose:
```bash
docker-compose up --build -d
```

4. Dostęp do aplikacji:
Po prawidłowym uruchomieniu kontenerów, aplikacja serwująca skompilowany interfejs Angulara oraz nasłuchująca na połączenia WebSocket będzie dostępna pod adresem:
```text
http://localhost:5000
```

## Główne zdarzenia WebSockets (Socket.IO)

- `tworz_pokoj` - Tworzy nową instancję pokoju, generuje kod dostępu i zwraca token Hosta.
- `dolacz` - Weryfikuje kod i pozwala nowemu graczowi dołączyć do istniejącego pokoju.
- `dodaj_bota` - Pozwala Hostowi na dodanie gracza sterowanego przez skrypt do wolnego miejsca w pokoju.
- `start_gry` - Inicjuje stan gry, rozdaje karty i rozpoczyna rozgrywkę.
- `wykonaj_ruch` - Przyjmuje akcję od aktualnego gracza (np. rzucenie pasującej karty, dobranie z talii).
- `wznow_sesje` - Pozwala na powrót do trwającej gry w przypadku odświeżenia strony (wymaga ważnego tokenu).
- `aktualizacja_stolu` (Zdarzenie wychodzące) - Rozsyła najnowszy stan gry, ułożenie kart oraz logi tury do wszystkich graczy w pokoju.