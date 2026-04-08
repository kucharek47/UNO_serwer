import os
import random
import uuid
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, join_room, emit
import bazy
import logika_serwerowa
from gra_w_uno import srodowisko_uno

sciezka_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), 'dist/UNOFront/browser'))

app = Flask(__name__, static_folder=sciezka_dist, static_url_path='/')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

with app.app_context():
    bazy.inicjalizuj_baze()


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serwuj_angular(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')


def wyslij_zaktualizowany_stan(pokoj_id, logi=None):
    nowe_pelne_dane = bazy.pobierz_pelny_pokoj(pokoj_id)
    nowe_dane_graczy = bazy.pobierz_graczy(pokoj_id)
    nowe_dane_kart = bazy.pobierz_karty(pokoj_id)
    tokeny_graczy = bazy.pobierz_tokeny_graczy(pokoj_id)
    kod_pokoju = nowe_pelne_dane['kod_dostepu']

    for gracz in nowe_dane_graczy:
        if not gracz['czy_bot']:
            token = tokeny_graczy.get(gracz['id'])
            zfiltrowane_karty = [
                k for k in nowe_dane_kart
                if k['lokalizacja'] == 'stos' or (k['lokalizacja'] == 'reka' and k['gracz_id'] == gracz['id'])
            ]
            stan_do_wyslania = {
                'pokoj': nowe_pelne_dane,
                'gracze': nowe_dane_graczy,
                'karty': zfiltrowane_karty,
                'logi': logi or []
            }
            if token:
                emit('aktualizacja_stolu', stan_do_wyslania, room=token, include_self=True)
            else:
                emit('aktualizacja_stolu', stan_do_wyslania, room=kod_pokoju, include_self=True)


@socketio.on('tworz_pokoj')
def tworz_pokoj(dane):
    ip_adres = request.remote_addr
    nazwa_gracza = dane.get('nazwa', 'Host')

    if not bazy.sprawdz_limit_host(ip_adres):
        return {'status': 'blad', 'wiadomosc': 'Limit czasu, sprobuj ponownie za 2 minuty.'}

    kod = str(random.randint(100000, 999999))
    pokoj_id = bazy.utworz_pokoj(kod, ip_adres)
    token = uuid.uuid4().hex

    bazy.dodaj_gracza(pokoj_id, 0, nazwa_gracza, False, token)

    join_room(kod)
    join_room(token)
    return {'status': 'ok', 'kod': kod, 'token': token, 'numer_gracza': 0}


@socketio.on('dolacz')
def dolacz(dane):
    kod = dane.get('kod')
    nazwa_gracza = dane.get('nazwa', 'Gracz')
    wynik = bazy.znajdz_pokoj_i_wolne_miejsce(kod)

    if not wynik:
        return {'status': 'blad', 'wiadomosc': 'Nie znaleziono pokoju lub osiagnieto limit graczy.'}

    pokoj_id, numer_gracza = wynik
    token = uuid.uuid4().hex

    bazy.dodaj_gracza(pokoj_id, numer_gracza, nazwa_gracza, False, token)

    join_room(kod)
    join_room(token)
    emit('nowy_gracz', {'numer': numer_gracza, 'nazwa': nazwa_gracza, 'czy_bot': False}, room=kod, include_self=True)
    return {'status': 'ok', 'kod': kod, 'token': token, 'numer_gracza': numer_gracza}


@socketio.on('dodaj_bota')
def dodaj_bota(dane):
    token = dane.get('token')
    weryfikacja = bazy.pobierz_id_po_tokenie(token)

    if not weryfikacja:
        return {'status': 'blad', 'wiadomosc': 'Nieprawidlowy token sesji.'}

    pokoj_id, _, numer_w_pokoju = weryfikacja

    if numer_w_pokoju != 0:
        return {'status': 'blad', 'wiadomosc': 'Tylko host moze dodac bota.'}

    dane_pokoju = bazy.pobierz_pelny_pokoj(pokoj_id)
    if dane_pokoju['status'] != 'oczekuje':
        return {'status': 'blad', 'wiadomosc': 'Gra juz sie rozpoczela.'}

    gracze = bazy.pobierz_graczy(pokoj_id)
    zajete_numery = [g['numer_w_pokoju'] for g in gracze]

    if len(zajete_numery) >= 5:
        return {'status': 'blad', 'wiadomosc': 'Brak miejsc w pokoju.'}

    wolny_numer = 0
    while wolny_numer in zajete_numery:
        wolny_numer += 1

    nazwa_bota = f"Bot {wolny_numer}"

    bazy.dodaj_gracza(pokoj_id, wolny_numer, nazwa_bota, True, uuid.uuid4().hex)

    emit('nowy_gracz', {'numer': wolny_numer, 'nazwa': nazwa_bota, 'czy_bot': True}, room=dane_pokoju['kod_dostepu'],
         include_self=True)
    return {'status': 'ok', 'numer_bota': wolny_numer}


@socketio.on('start_gry')
def start_gry(dane):
    token = dane.get('token')
    weryfikacja = bazy.pobierz_id_po_tokenie(token)

    if not weryfikacja:
        return {'status': 'blad', 'wiadomosc': 'Nieprawidlowy token sesji.'}

    pokoj_id, _, numer_w_pokoju = weryfikacja

    if numer_w_pokoju != 0:
        return {'status': 'blad', 'wiadomosc': 'Tylko host moze wystartowac gre.'}

    dane_pokoju = bazy.pobierz_pelny_pokoj(pokoj_id)

    if dane_pokoju['status'] != 'oczekuje':
        return {'status': 'blad', 'wiadomosc': 'Gra juz sie rozpoczela.'}

    gracze = bazy.pobierz_graczy(pokoj_id)

    if len(gracze) < 2:
        return {'status': 'blad', 'wiadomosc': 'Zbyt malo graczy do startu.'}

    bazy.zmien_status_pokoju(pokoj_id, 'w_trakcie')

    srodowisko = srodowisko_uno(len(gracze), max_graczy=5, nowa_gra=True)

    stan_pokoju, karty_dane, aktualizacje_graczy = logika_serwerowa.pobierz_dane_do_zapisu(srodowisko, pokoj_id, gracze)

    bazy.zapisz_stan_gry(pokoj_id, stan_pokoju, karty_dane)
    bazy.zaktualizuj_stan_graczy(aktualizacje_graczy)

    wyslij_zaktualizowany_stan(pokoj_id, srodowisko.silnik.logi)

    dane_graczy_nowe = bazy.pobierz_graczy(pokoj_id)
    id_aktualnego = srodowisko.silnik.aktualny_gracz

    if dane_graczy_nowe[id_aktualnego]['czy_bot']:
        dane_pokoju_nowe = bazy.pobierz_pelny_pokoj(pokoj_id)
        dane_kart_nowe = bazy.pobierz_karty(pokoj_id)
        logi_botow = logika_serwerowa.obsluz_ture_gry(pokoj_id, dane_pokoju_nowe, dane_graczy_nowe, dane_kart_nowe,
                                                      None)
        wyslij_zaktualizowany_stan(pokoj_id, logi_botow)

    return {'status': 'ok'}


@socketio.on('wznow_sesje')
def wznow_sesje(dane):
    token = dane.get('token')
    dane_weryfikacji = bazy.pobierz_id_po_tokenie(token)

    if not dane_weryfikacji:
        return {'status': 'blad', 'wiadomosc': 'Nieprawidlowy token sesji.'}

    pokoj_id, _, numer_gracza = dane_weryfikacji

    dane_pokoju = bazy.pobierz_pelny_pokoj(pokoj_id)
    dane_graczy = bazy.pobierz_graczy(pokoj_id)
    dane_kart = bazy.pobierz_karty(pokoj_id)

    kod_pokoju = dane_pokoju['kod_dostepu']
    join_room(kod_pokoju)
    join_room(token)

    stan_gry = {
        'pokoj': dane_pokoju,
        'gracze': dane_graczy,
        'karty': dane_kart,
        'logi': []
    }
    return {'status': 'ok', 'stan_gry': stan_gry, 'numer_gracza': numer_gracza}


@socketio.on('wykonaj_ruch')
def wykonaj_ruch(dane):
    token = dane.get('token')
    akcja = dane.get('akcja')
    print(f"[DEBUG] Otrzymano probe wykonania akcji: {akcja} od tokenu: {token}")

    dane_weryfikacji = bazy.pobierz_id_po_tokenie(token)
    if not dane_weryfikacji:
        print("[ERROR] Nieprawidlowy token sesji.")
        return {'status': 'blad', 'wiadomosc': 'Nieprawidlowy token sesji.'}

    pokoj_id, id_gracza_baza, numer_w_pokoju = dane_weryfikacji
    pelne_dane_pokoju = bazy.pobierz_pelny_pokoj(pokoj_id)

    if pelne_dane_pokoju['status'] == 'zakonczona':
        print("[DEBUG] Gra juz zakonczona, odrzucam ruch.")
        return {'status': 'blad', 'wiadomosc': 'Gra juz sie zakonczyla.'}

    dane_graczy = bazy.pobierz_graczy(pokoj_id)
    dane_kart = bazy.pobierz_karty(pokoj_id)

    if pelne_dane_pokoju['aktualny_gracz'] != numer_w_pokoju:
        print(
            f"[DEBUG] Odrzucono ruch - to tura gracza {pelne_dane_pokoju['aktualny_gracz']}, a probowal gracz {numer_w_pokoju}.")
        return {'status': 'blad', 'wiadomosc': 'To nie jest twoja tura.'}

    logi = logika_serwerowa.obsluz_ture_gry(pokoj_id, pelne_dane_pokoju, dane_graczy, dane_kart, akcja)
    print(f"[DEBUG] Logi z tury: {logi}")

    wyslij_zaktualizowany_stan(pokoj_id, logi)
    return {'status': 'ok'}


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=13007, allow_unsafe_werkzeug=True)