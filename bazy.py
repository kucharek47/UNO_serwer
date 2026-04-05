import os
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL")
engine = create_engine(url)

def inicjalizuj_baze():
    zapytania = [
        """
        CREATE TABLE IF NOT EXISTS pokoje (
            id SERIAL PRIMARY KEY,
            kod_dostepu VARCHAR(6) UNIQUE NOT NULL,
            status VARCHAR(20) DEFAULT 'oczekuje',
            aktualny_gracz INT,
            kierunek INT DEFAULT 1,
            aktualny_kolor VARCHAR(15),
            kara INT DEFAULT 0,
            ile_stopow INT DEFAULT 0,
            aktywne_combo VARCHAR(10),
            utworzono TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS gracze (
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
        CREATE TABLE IF NOT EXISTS karty (
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
        CREATE TABLE IF NOT EXISTS limity_tworzenia (
            ip_adres VARCHAR(45) PRIMARY KEY,
            ostatnie_utworzenie TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]

    with engine.begin() as conn:
        for sql in zapytania:
            conn.execute(text(sql))

def sprawdz_limit_host(ip_adres):
    with engine.connect() as conn:
        wynik = conn.execute(text("""
            SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ostatnie_utworzenie)) 
            FROM limity_tworzenia WHERE ip_adres = :ip
        """), {"ip": ip_adres}).scalar()

        if wynik is not None and wynik < 120:
            return False
        return True

def utworz_pokoj(kod, ip_adres):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO limity_tworzenia (ip_adres, ostatnie_utworzenie)
            VALUES (:ip, CURRENT_TIMESTAMP)
            ON CONFLICT (ip_adres) DO UPDATE 
            SET ostatnie_utworzenie = CURRENT_TIMESTAMP;
        """), {"ip": ip_adres})

        wynik = conn.execute(text("""
            INSERT INTO pokoje (kod_dostepu) 
            VALUES (:kod) RETURNING id;
        """), {"kod": kod})
        return wynik.scalar()

def dodaj_gracza(pokoj_id, numer, czy_bot, token):
    with engine.begin() as conn:
        wynik = conn.execute(text("""
            INSERT INTO gracze (pokoj_id, numer_w_pokoju, czy_bot, token) 
            VALUES (:pokoj_id, :numer, :czy_bot, :token) RETURNING id;
        """), {"pokoj_id": pokoj_id, "numer": numer, "czy_bot": czy_bot, "token": token})
        return wynik.scalar()

def zapisz_stan_gry(pokoj_id, stan_pokoju, karty_dane):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE pokoje 
            SET aktualny_gracz = :aktualny_gracz, kierunek = :kierunek, 
                aktualny_kolor = :aktualny_kolor, kara = :kara, 
                ile_stopow = :ile_stopow, aktywne_combo = :aktywne_combo
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
            SELECT kolor, wartosc FROM karty 
            WHERE pokoj_id = :pokoj_id AND lokalizacja = 'stos' 
            ORDER BY pozycja ASC
        """), {"pokoj_id": pokoj_id})
        return wynik.fetchall()