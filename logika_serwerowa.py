import onnxruntime as ort
import numpy as np
from gra_w_uno import srodowisko_uno, karta
import bazy

sesja_onnx = ort.InferenceSession("model_uno_v10.onnx")

def odtworz_srodowisko(dane_pokoju, dane_graczy, dane_kart):
    liczba_graczy = len(dane_graczy)
    srodowisko = srodowisko_uno(liczba_graczy, max_graczy=5, nowa_gra=False)

    srodowisko.silnik.aktualny_gracz = dane_pokoju['aktualny_gracz']
    srodowisko.silnik.kierunek = dane_pokoju['kierunek']
    srodowisko.silnik.aktualny_kolor = dane_pokoju['aktualny_kolor']
    srodowisko.silnik.aktualna_kara = dane_pokoju['kara']
    srodowisko.silnik.ile_stopow = dane_pokoju['ile_stopow']
    srodowisko.silnik.aktywne_combo = dane_pokoju['aktywne_combo']

    srodowisko.silnik.stos = []
    srodowisko.silnik.talia_gry.karty = []
    srodowisko.silnik.wyrzucone_karty = []
    for g in srodowisko.silnik.gracze:
        g.reka = []

    karty_posortowane = sorted(dane_kart, key=lambda x: x['pozycja'])

    for k in karty_posortowane:
        nowa_karta = karta(k['kolor'], k['wartosc'])
        if k['lokalizacja'] == 'stos':
            srodowisko.silnik.stos.append(nowa_karta)
            srodowisko.silnik.wyrzucone_karty.append(nowa_karta)
        elif k['lokalizacja'] == 'talia':
            srodowisko.silnik.talia_gry.karty.append(nowa_karta)
        elif k['lokalizacja'] == 'reka':
            idx_gracza = next(i for i, gr in enumerate(dane_graczy) if gr['id'] == k['gracz_id'])
            srodowisko.silnik.gracze[idx_gracza].dobierz_karte(nowa_karta)

    for i, g_dane in enumerate(dane_graczy):
        srodowisko.silnik.gracze[i].zglasza_uno = g_dane['zglasza_uno']
        srodowisko.silnik.gracze[i].pominiete_tury = g_dane['pominiete_tury']

    return srodowisko, dane_graczy

def pobierz_dane_do_zapisu(srodowisko, pok_id, gracze_dane):
    stan_pokoju = {
        'pokoj_id': pok_id,
        'aktualny_gracz': srodowisko.silnik.aktualny_gracz,
        'kierunek': srodowisko.silnik.kierunek,
        'aktualny_kolor': srodowisko.silnik.aktualny_kolor,
        'kara': srodowisko.silnik.aktualna_kara,
        'ile_stopow': srodowisko.silnik.ile_stopow,
        'aktywne_combo': srodowisko.silnik.aktywne_combo
    }

    karty_dane = []
    pozycja_stosu = 0
    for k in srodowisko.silnik.stos:
        karty_dane.append({
            'pokoj_id': pok_id, 'gracz_id': None, 'lokalizacja': 'stos',
            'pozycja': pozycja_stosu, 'kolor': k.kolor, 'wartosc': k.wartosc
        })
        pozycja_stosu += 1

    pozycja_talii = 0
    for k in srodowisko.silnik.talia_gry.karty:
        karty_dane.append({
            'pokoj_id': pok_id, 'gracz_id': None, 'lokalizacja': 'talia',
            'pozycja': pozycja_talii, 'kolor': k.kolor, 'wartosc': k.wartosc
        })
        pozycja_talii += 1

    for i, g in enumerate(srodowisko.silnik.gracze):
        id_bazy_gracza = gracze_dane[i]['id']
        for poz, k in enumerate(g.reka):
            karty_dane.append({
                'pokoj_id': pok_id, 'gracz_id': id_bazy_gracza, 'lokalizacja': 'reka',
                'pozycja': poz, 'kolor': k.kolor, 'wartosc': k.wartosc
            })

    aktualizacje_graczy = []
    for i, g in enumerate(srodowisko.silnik.gracze):
        aktualizacje_graczy.append({
            'id': gracze_dane[i]['id'],
            'zglasza_uno': g.zglasza_uno,
            'pominiete_tury': g.pominiete_tury
        })

    return stan_pokoju, karty_dane, aktualizacje_graczy

def wykonaj_ruch_bota(srodowisko, id_gracza):
    stan = srodowisko.pobierz_stan(id_gracza)
    maska = srodowisko.pobierz_maske_akcji(id_gracza)

    stan_array = np.array(stan, dtype=np.float32).reshape(1, -1)
    wyjscie_onnx = sesja_onnx.run(None, {"stan": stan_array})[0][0]

    for i in range(len(maska)):
        if maska[i] == 0:
            wyjscie_onnx[i] = -np.inf

    akcja = int(np.argmax(wyjscie_onnx))
    _, _, czy_koniec = srodowisko.wykonaj_krok(id_gracza, akcja)
    return czy_koniec

def obsluz_ture_gry(pokoj_id, dane_pokoju, dane_graczy, dane_kart, akcja_czlowieka=None):
    srodowisko, gracze_dane = odtworz_srodowisko(dane_pokoju, dane_graczy, dane_kart)
    id_aktualnego = srodowisko.silnik.aktualny_gracz
    czy_koniec = False

    if akcja_czlowieka is not None and not gracze_dane[id_aktualnego]['czy_bot']:
        _, _, czy_koniec = srodowisko.wykonaj_krok(id_aktualnego, akcja_czlowieka)

    while not czy_koniec:
        id_kolejnego = srodowisko.silnik.aktualny_gracz
        if len(srodowisko.silnik.ranking) > 0:
            czy_koniec = True
            break
        if not gracze_dane[id_kolejnego]['czy_bot']:
            break

        czy_koniec = wykonaj_ruch_bota(srodowisko, id_kolejnego)

    if czy_koniec:
        bazy.zmien_status_pokoju(pokoj_id, 'zakonczona')

    stan_pokoju, karty_dane, aktualizacje_graczy = pobierz_dane_do_zapisu(srodowisko, pokoj_id, gracze_dane)

    bazy.zapisz_stan_gry(pokoj_id, stan_pokoju, karty_dane)
    bazy.zaktualizuj_stan_graczy(aktualizacje_graczy)

    return srodowisko.silnik.logi