import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("DATABASE_URL")
engine = create_engine(url)


def inicjalizuj_baze():
    zapytania = [
        """
        CREATE TABLE IF NOT EXISTS pokoje
        (
            id SERIAL PRIMARY KEY,
            kod_dostepu VARCHAR(6) UNIQUE NOT NULL,
            status VARCHAR(20) DEFAULT 'oczekuje',
            aktualny_gracz INT,
            kierunek INT DEFAULT 1,
            aktualny_kolor VARCHAR(15),
            kara INT DEFAULT 0,
            ile_stopow INT DEFAULT 0,
            aktywne_combo VARCHAR(20),
            utworzono TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS gracze
        (
            id SERIAL PRIMARY KEY,
            pokoj_id INT REFERENCES pokoje(id) ON DELETE CASCADE,
            numer_w_pokoju INT,
            czy_bot BOOLEAN DEFAULT FALSE,
            zglasza_uno BOOLEAN DEFAULT FALSE,
            pominiete_tury INT DEFAULT 0,
            token VARCHAR(36) UNIQUE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS karty
        (
            id SERIAL PRIMARY KEY,
            pokoj_id INT REFERENCES pokoje(id) ON DELETE CASCADE,
            gracz_id INT REFERENCES gracze(id) ON DELETE CASCADE,
            lokalizacja VARCHAR(10),
            pozycja INT,
            kolor VARCHAR(15),
            wartosc VARCHAR(20)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS limity_tworzenia
        (
            ip_adres VARCHAR(45) PRIMARY KEY,
            ostatnie_utworzenie TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]

    with engine.begin() as conn:
        for sql in zapytania:
            conn.execute(text(sql))
        conn.execute(text("ALTER TABLE gracze ADD COLUMN IF NOT EXISTS nazwa VARCHAR(50) DEFAULT 'Gracz';"))
        conn.execute(text("ALTER TABLE pokoje ALTER COLUMN aktywne_combo TYPE VARCHAR(20);"))

def sprawdz_limit_host(ip_adres):
    with engine.connect() as conn:
        wynik = conn.execute(text("""
            SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ostatnie_utworzenie))
            FROM limity_tworzenia
            WHERE ip_adres = :ip
        """), {"ip": ip_adres}).scalar()

        if wynik is not None and wynik < 120:
            return False
        return True


def utworz_pokoj(kod, ip_adres):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO limity_tworzenia (ip_adres, ostatnie_utworzenie)
            VALUES (:ip, CURRENT_TIMESTAMP) ON CONFLICT (ip_adres) DO
            UPDATE SET ostatnie_utworzenie = CURRENT_TIMESTAMP;
        """), {"ip": ip_adres})

        wynik = conn.execute(text("""
            INSERT INTO pokoje (kod_dostepu)
            VALUES (:kod) RETURNING id;
        """), {"kod": kod})
        return wynik.scalar()


def dodaj_gracza(pokoj_id, numer, nazwa, czy_bot, token):
    with engine.begin() as conn:
        wynik = conn.execute(text("""
            INSERT INTO gracze (pokoj_id, numer_w_pokoju, nazwa, czy_bot, token)
            VALUES (:pokoj_id, :numer, :nazwa, :czy_bot, :token) RETURNING id;
        """), {"pokoj_id": pokoj_id, "numer": numer, "nazwa": nazwa, "czy_bot": czy_bot, "token": token})
        return wynik.scalar()


def zapisz_stan_gry(pokoj_id, stan_pokoju, karty_dane):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE pokoje
            SET aktualny_gracz = :aktualny_gracz,
                kierunek       = :kierunek,
                aktualny_kolor = :aktualny_kolor,
                kara           = :kara,
                ile_stopow     = :ile_stopow,
                aktywne_combo  = :aktywne_combo
            WHERE id = :pokoj_id
        """), stan_pokoju)

        conn.execute(text("DELETE FROM karty WHERE pokoj_id = :pokoj_id"), {"pokoj_id": pokoj_id})

        for k in karty_dane:
            conn.execute(text("""
                INSERT INTO karty (pokoj_id, gracz_id, lokalizacja, pozycja, kolor, wartosc)
                VALUES (:pokoj_id, :gracz_id, :lokalizacja, :pozycja, :kolor, :wartosc)
            """), k)


def pobierz_historie_stosu(pokoj_id):
    with engine.connect() as conn:
        wynik = conn.execute(text("""
            SELECT kolor, wartosc
            FROM karty
            WHERE pokoj_id = :pokoj_id
              AND lokalizacja = 'stos'
            ORDER BY pozycja ASC
        """), {"pokoj_id": pokoj_id})
        return wynik.fetchall()


def znajdz_pokoj_i_wolne_miejsce(kod):
    with engine.begin() as conn:
        wynik_pokoju = conn.execute(text("SELECT id FROM pokoje WHERE kod_dostepu = :kod AND status = 'oczekuje'"),
                                    {"kod": kod}).fetchone()
        if not wynik_pokoju:
            return None

        pokoj_id = wynik_pokoju[0]

        wynik_graczy = conn.execute(text("SELECT numer_w_pokoju FROM gracze WHERE pokoj_id = :pokoj_id"),
                                    {"pokoj_id": pokoj_id}).fetchall()
        zajete_numery = [w[0] for w in wynik_graczy]

        if len(zajete_numery) >= 5:
            return None

        wolny_numer = 0
        while wolny_numer in zajete_numery:
            wolny_numer += 1

        return pokoj_id, wolny_numer


def pobierz_stan_dla_tokenu(token):
    with engine.connect() as conn:
        dane_weryfikacji = conn.execute(text("""
            SELECT p.id, p.kod_dostepu, p.status, p.aktualny_gracz, p.kierunek, p.aktualny_kolor, p.kara, p.ile_stopow, p.aktywne_combo, g.numer_w_pokoju
            FROM gracze g
            JOIN pokoje p ON g.pokoj_id = p.id
            WHERE g.token = :token
        """), {"token": token}).fetchone()

        if not dane_weryfikacji:
            return None

        pokoj_id = dane_weryfikacji[0]

        karty = conn.execute(text("""
            SELECT gracz_id, lokalizacja, pozycja, kolor, wartosc
            FROM karty
            WHERE pokoj_id = :pokoj_id
        """), {"pokoj_id": pokoj_id}).fetchall()

        gracze = conn.execute(text("""
            SELECT id, numer_w_pokoju, nazwa, czy_bot, zglasza_uno, pominiete_tury
            FROM gracze
            WHERE pokoj_id = :pokoj_id
        """), {"pokoj_id": pokoj_id}).fetchall()

        return {
            "kod_dostepu": dane_weryfikacji[1],
            "status": dane_weryfikacji[2],
            "aktualny_gracz": dane_weryfikacji[3],
            "kierunek": dane_weryfikacji[4],
            "aktualny_kolor": dane_weryfikacji[5],
            "kara": dane_weryfikacji[6],
            "ile_stopow": dane_weryfikacji[7],
            "aktywne_combo": dane_weryfikacji[8],
            "twoj_numer": dane_weryfikacji[9],
            "karty": [{"gracz_id": k[0], "lokalizacja": k[1], "pozycja": k[2], "kolor": k[3], "wartosc": k[4]} for k in karty],
            "gracze": [{"id": g[0], "numer_w_pokoju": g[1], "nazwa": g[2], "czy_bot": g[3], "zglasza_uno": g[4], "pominiete_tury": g[5]} for g in gracze]
        }


def pobierz_id_po_tokenie(token):
    with engine.connect() as conn:
        wynik = conn.execute(text("SELECT pokoj_id, id, numer_w_pokoju FROM gracze WHERE token = :token"),
                             {"token": token}).fetchone()
        if wynik:
            return wynik[0], wynik[1], wynik[2]
        return None


def pobierz_pelny_pokoj(pokoj_id):
    with engine.connect() as conn:
        wynik = conn.execute(text("""
            SELECT id, kod_dostepu, status, aktualny_gracz, kierunek, aktualny_kolor, kara, ile_stopow, aktywne_combo
            FROM pokoje
            WHERE id = :pokoj_id
        """), {"pokoj_id": pokoj_id}).fetchone()

        if wynik:
            return {
                "id": wynik[0],
                "kod_dostepu": wynik[1],
                "status": wynik[2],
                "aktualny_gracz": wynik[3],
                "kierunek": wynik[4],
                "aktualny_kolor": wynik[5],
                "kara": wynik[6],
                "ile_stopow": wynik[7],
                "aktywne_combo": wynik[8]
            }
        return None


def pobierz_graczy(pokoj_id):
    with engine.connect() as conn:
        wynik = conn.execute(text("""
            SELECT id, numer_w_pokoju, nazwa, czy_bot, zglasza_uno, pominiete_tury
            FROM gracze
            WHERE pokoj_id = :pokoj_id
            ORDER BY numer_w_pokoju ASC
        """), {"pokoj_id": pokoj_id}).fetchall()
        return [{"id": g[0], "numer_w_pokoju": g[1], "nazwa": g[2], "czy_bot": g[3], "zglasza_uno": g[4], "pominiete_tury": g[5]} for g in wynik]

def pobierz_karty(pokoj_id):
    with engine.connect() as conn:
        wynik = conn.execute(text("""
            SELECT id, gracz_id, lokalizacja, pozycja, kolor, wartosc
            FROM karty
            WHERE pokoj_id = :pokoj_id
        """), {"pokoj_id": pokoj_id}).fetchall()

        return [{"id": k[0], "gracz_id": k[1], "lokalizacja": k[2], "pozycja": k[3], "kolor": k[4], "wartosc": k[5]} for k in wynik]


def zaktualizuj_stan_graczy(aktualizacje):
    with engine.begin() as conn:
        for akt in aktualizacje:
            conn.execute(text("""
                UPDATE gracze
                SET zglasza_uno    = :zglasza_uno,
                    pominiete_tury = :pominiete_tury
                WHERE id = :id
            """), akt)


def zmien_status_pokoju(pokoj_id, nowy_status):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE pokoje 
            SET status = :status 
            WHERE id = :pokoj_id
        """), {"status": nowy_status, "pokoj_id": pokoj_id})

def pobierz_tokeny_graczy(pokoj_id):
    with engine.connect() as conn:
        wynik = conn.execute(text("SELECT id, token FROM gracze WHERE pokoj_id = :pokoj_id"), {"pokoj_id": pokoj_id}).fetchall()
        return {w[0]: w[1] for w in wynik}