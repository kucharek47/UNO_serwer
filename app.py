import os
import random
import uuid
from flask import Flask, request
from flask_socketio import SocketIO, join_room, emit
import bazy
import logika_serwerowa
from gra_w_uno import srodowisko_uno

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

with app.app_context():
    bazy.inicjalizuj_baze()


@socketio.on('tworz_pokoj')
def tworz_pokoj(dane):
    ip_adres = request.remote_addr

    if not bazy.sprawdz_limit_host(ip_adres):
        return {'status': 'blad', 'wiadomosc': 'Limit czasu, sprobuj ponownie za 2 minuty.'}

    kod = str(random.randint(100000, 999999))
    pokoj_id = bazy.utworz_pokoj(kod, ip_adres)
    token = uuid.uuid4().hex

    bazy.dodaj_gracza(pokoj_id, 0, False, token)

    join_room(kod)
    return {'status': 'ok', 'kod': kod, 'token': token, 'numer_gracza': 0}


@socketio.on('dolacz')
def dolacz(dane):
    kod = dane.get('kod')
    wynik = bazy.znajdz_pokoj_i_wolne_miejsce(kod)

    if not wynik:
        return {'status': 'blad', 'wiadomosc': 'Nie znaleziono pokoju lub osiagnieto limit graczy.'}

    pokoj_id, numer_gracza = wynik
    token = uuid.uuid4().hex

    bazy.dodaj_gracza(pokoj_id, numer_gracza, False, token)

    join_room(kod)
    emit('nowy_gracz', {'numer': numer_gracza, 'czy_bot': False}, room=kod)
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

    bazy.dodaj_gracza(pokoj_id, wolny_numer, True, uuid.uuid4().hex)
    emit('nowy_gracz', {'numer': wolny_numer, 'czy_bot': True}, room=dane_pokoju['kod_dostepu'])
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

    # DODANA WALIDACJA: Blokada restartowania już trwającej gry
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

    nowe_pelne_dane = bazy.pobierz_pelny_pokoj(pokoj_id)
    nowe_dane_graczy = bazy.pobierz_graczy(pokoj_id)
    nowe_dane_kart = bazy.pobierz_karty(pokoj_id)

    stan_do_wyslania = {
        'pokoj': nowe_pelne_dane,
        'gracze': nowe_dane_graczy,
        'karty': nowe_dane_kart,
        'logi': srodowisko.silnik.logi
    }

    emit('aktualizacja_stolu', stan_do_wyslania, room=dane_pokoju['kod_dostepu'])

    id_aktualnego = srodowisko.silnik.aktualny_gracz
    if nowe_dane_graczy[id_aktualnego]['czy_bot']:
        # POPRAWKA: Przechwytujemy logi bota i wysyłamy je do graczy
        logi_botow = logika_serwerowa.obsluz_ture_gry(pokoj_id, nowe_pelne_dane, nowe_dane_graczy, nowe_dane_kart, None)

        nowe_pelne_dane_po_bocie = bazy.pobierz_pelny_pokoj(pokoj_id)
        nowe_dane_graczy_po_bocie = bazy.pobierz_graczy(pokoj_id)
        nowe_dane_kart_po_bocie = bazy.pobierz_karty(pokoj_id)

        stan_do_wyslania_po_bocie = {
            'pokoj': nowe_pelne_dane_po_bocie,
            'gracze': nowe_dane_graczy_po_bocie,
            'karty': nowe_dane_kart_po_bocie,
            'logi': logi_botow
        }
        emit('aktualizacja_stolu', stan_do_wyslania_po_bocie, room=dane_pokoju['kod_dostepu'])

    return {'status': 'ok'}


@socketio.on('wznow_sesje')
def wznow_sesje(dane):
    token = dane.get('token')
    dane_pokoju = bazy.pobierz_stan_dla_tokenu(token)

    if not dane_pokoju:
        return {'status': 'blad', 'wiadomosc': 'Nieprawidlowy token sesji.'}

    kod_pokoju = dane_pokoju['kod_dostepu']
    join_room(kod_pokoju)
    return {'status': 'ok', 'stan_gry': dane_pokoju}


@socketio.on('wykonaj_ruch')
def wykonaj_ruch(dane):
    token = dane.get('token')
    akcja = dane.get('akcja')

    dane_weryfikacji = bazy.pobierz_id_po_tokenie(token)
    if not dane_weryfikacji:
        return {'status': 'blad', 'wiadomosc': 'Nieprawidlowy token sesji.'}

    pokoj_id, id_gracza_baza, numer_w_pokoju = dane_weryfikacji

    pelne_dane_pokoju = bazy.pobierz_pelny_pokoj(pokoj_id)

    if pelne_dane_pokoju['status'] == 'zakonczona':
        return {'status': 'blad', 'wiadomosc': 'Gra juz sie zakonczyla.'}

    dane_graczy = bazy.pobierz_graczy(pokoj_id)
    dane_kart = bazy.pobierz_karty(pokoj_id)

    if pelne_dane_pokoju['aktualny_gracz'] != numer_w_pokoju:
        return {'status': 'blad', 'wiadomosc': 'To nie jest twoja tura.'}

    logi = logika_serwerowa.obsluz_ture_gry(pokoj_id, pelne_dane_pokoju, dane_graczy, dane_kart, akcja)

    nowe_pelne_dane = bazy.pobierz_pelny_pokoj(pokoj_id)
    nowe_dane_graczy = bazy.pobierz_graczy(pokoj_id)
    nowe_dane_kart = bazy.pobierz_karty(pokoj_id)

    stan_do_wyslania = {
        'pokoj': nowe_pelne_dane,
        'gracze': nowe_dane_graczy,
        'karty': nowe_dane_kart,
        'logi': logi
    }

    emit('aktualizacja_stolu', stan_do_wyslania, room=pelne_dane_pokoju['kod_dostepu'])
    return {'status': 'ok'}


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)