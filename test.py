import socketio
import time

klient = socketio.Client()
sesja = {}
licznik = 0

@klient.event
def connect():
    print("Polaczono z serwerem")
    klient.emit('tworz_pokoj', {}, callback=etap_jeden)

def etap_jeden(dane):
    sesja['token'] = dane['token']
    sesja['kod'] = dane['kod']
    print(f"Pokoj utworzony, kod: {sesja['kod']}")
    klient.emit('dodaj_bota', {'token': sesja['token']}, callback=etap_dwa)

def etap_dwa(dane):
    print("Dodano pierwszego bota")
    klient.emit('dodaj_bota', {'token': sesja['token']}, callback=etap_trzy)

def etap_trzy(dane):
    print("Dodano drugiego bota")
    klient.emit('start_gry', {'token': sesja['token']}, callback=etap_cztery)

def etap_cztery(dane):
    print("Zadanie startu gry zostalo wyslane")

@klient.on('aktualizacja_stolu')
def na_aktualizacje(dane):
    global licznik
    pokoj = dane['pokoj']
    logi = dane['logi']

    for wpis in logi:
        print(f"SERWER: {wpis}")

    if pokoj['status'] == 'zakonczona':
        print("\n--- GRA ZAKONCZONA (KTOS WYGRAL) ---")
        klient.disconnect()
        return

    if pokoj['aktualny_gracz'] == 0:
        if licznik >= 10:
            print("Wykonano 10 ruchow, konczenie polaczenia")
            klient.disconnect()
            return

        licznik += 1
        print(f"--- WYKONUJE RUCH {licznik}/10 (PAS/DOBRANIE) ---")
        time.sleep(1.5)
        klient.emit('wykonaj_ruch', {'token': sesja['token'], 'akcja': 60})

if __name__ == '__main__':
    klient.connect('http://localhost:5000')
    klient.wait()