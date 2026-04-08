import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def sprawdz_polaczenie():
    url = os.environ.get("DATABASE_URL")

    if not url:
        print("brak .env")
        return

    print(f"{url.split('@')[-1]}")

    try:
        engine = create_engine(url, connect_args={'connect_timeout': 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✅ Połączenie z bazą danych: OK")
            result = conn.execute(text("""
                                       SELECT table_name
                                       FROM information_schema.tables
                                       WHERE table_schema = 'public'
                                       """))
            tabele = [row[0] for row in result]

            if tabele:
                print(f"✅ Znalezione tabele: {', '.join(tabele)}")
            else:
                print("ℹ️ Połączono pomyślnie, ale baza jest pusta (brak tabel).")

    except Exception as e:
        print("BŁĄD")
        print(f"{e}")


if __name__ == "__main__":
    sprawdz_polaczenie()