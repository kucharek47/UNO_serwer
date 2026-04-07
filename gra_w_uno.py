import random


class karta:
    def __init__(self, kolor, wartosc):
        self.kolor = kolor
        self.wartosc = wartosc

    def __str__(self):
        return f"{self.kolor} {self.wartosc}" if self.kolor else self.wartosc


class talia:
    def __init__(self):
        self.karty = []
        self.buduj()

    def buduj(self):
        kolory = ['czerwony', 'zielony', 'niebieski', 'zolty']
        wartosci = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'stop', 'zmiana_kierunku', '+2']
        specjalne = ['zmiana_koloru', '+4']

        for kolor in kolory:
            self.karty.append(karta(kolor, '0'))
            for wartosc in wartosci[1:]:
                self.karty.append(karta(kolor, wartosc))
                self.karty.append(karta(kolor, wartosc))

        for _ in range(4):
            for specjalna in specjalne:
                self.karty.append(karta(None, specjalna))

    def tasuj(self):
        random.shuffle(self.karty)

    def dobierz(self):
        return self.karty.pop() if self.karty else None


class gracz:
    def __init__(self, id_gracza):
        self.id_gracza = id_gracza
        self.reka = []
        self.zglasza_uno = False
        self.pominiete_tury = 0

    def dobierz_karte(self, k):
        self.reka.append(k)
        self.zglasza_uno = False

    def rzuc_karte(self, indeks):
        return self.reka.pop(indeks)


class gra:
    def __init__(self, liczba_graczy, nowa_gra=True):
        self.talia_gry = talia()
        self.gracze = [gracz(i) for i in range(liczba_graczy)]
        self.stos = []
        self.wyrzucone_karty = []
        self.aktualny_gracz = 0
        self.kierunek = 1
        self.aktualny_kolor = None
        self.aktualna_kara = 0
        self.ranking = []
        self.logi = []
        self.aktywne_combo = None
        self.ile_stopow = 0

        if nowa_gra:
            self.talia_gry.tasuj()
            self.rozdaj()
            self.rozpocznij()
        else:
            self.talia_gry.karty = []

    def dodaj_log(self, wiadomosc):
        self.logi.append(wiadomosc)

    def pobierz_karte(self):
        k = self.talia_gry.dobierz()
        if not k:
            if len(self.stos) > 1:
                ostatnia_karta = self.stos.pop()
                self.talia_gry.karty = self.stos
                self.talia_gry.tasuj()
                self.stos = [ostatnia_karta]
                self.wyrzucone_karty = []
                k = self.talia_gry.dobierz()
        return k

    def rozdaj(self):
        for _ in range(7):
            for g in self.gracze:
                nowa_karta = self.pobierz_karte()
                if nowa_karta:
                    g.dobierz_karte(nowa_karta)

    def rozpocznij(self):
        pierwsza_karta = self.pobierz_karte()
        while pierwsza_karta and pierwsza_karta.wartosc in ['zmiana_koloru', '+4']:
            self.talia_gry.karty.insert(0, pierwsza_karta)
            self.talia_gry.tasuj()
            pierwsza_karta = self.pobierz_karte()

        if pierwsza_karta:
            self.stos.append(pierwsza_karta)
            self.wyrzucone_karty.append(pierwsza_karta)
            self.aktualny_kolor = pierwsza_karta.kolor
            self.dodaj_log(f"Gra rozpoczyna sie od karty na stosie: {pierwsza_karta}")

    def nastepny_gracz(self):
        if len(self.ranking) >= len(self.gracze) - 1:
            return

        while True:
            self.aktualny_gracz = (self.aktualny_gracz + self.kierunek) % len(self.gracze)
            g = self.gracze[self.aktualny_gracz]
            if g.id_gracza not in self.ranking:
                if g.pominiete_tury > 0:
                    g.pominiete_tury -= 1
                else:
                    break

    def waliduj_ruch(self, k):
        if k.kolor is None:
            return True
        if k.kolor == self.aktualny_kolor:
            return True
        if self.stos and self.stos[-1].wartosc == k.wartosc:
            return True
        return False

    def zagraj_karte(self, id_gracza, indeks_karty, wybrany_kolor=None):
        g = self.gracze[id_gracza]
        k = g.rzuc_karte(indeks_karty)
        self.stos.append(k)
        self.wyrzucone_karty.append(k)

        if len(g.reka) > 1:
            g.zglasza_uno = False

        self.aktywne_combo = k.wartosc

        if k.kolor:
            self.aktualny_kolor = k.kolor
        else:
            self.aktualny_kolor = wybrany_kolor

        self.zastosuj_efekt(k)

        if len(g.reka) == 0:
            self.ranking.append(id_gracza)
            self.zakoncz_ture(id_gracza)
        return True

    def zastosuj_efekt(self, k):
        aktywni = len(self.gracze) - len(self.ranking)
        if k.wartosc == 'zmiana_kierunku':
            self.kierunek *= -1
            if aktywni == 2:
                self.ile_stopow += 1
        elif k.wartosc == 'stop':
            self.ile_stopow += 1
        elif k.wartosc == '+2':
            self.aktualna_kara += 2
        elif k.wartosc == '+4':
            self.aktualna_kara += 4

    def zakoncz_ture(self, id_gracza):
        self.aktywne_combo = None
        self.nastepny_gracz()
        return True

    def krzycz_uno(self, id_gracza):
        g = self.gracze[id_gracza]
        g.zglasza_uno = True
        return True

    def rozlicz_kare(self, id_gracza):
        g = self.gracze[id_gracza]
        for _ in range(self.aktualna_kara):
            k = self.pobierz_karte()
            if k:
                g.dobierz_karte(k)
        self.aktualna_kara = 0
        self.nastepny_gracz()
        return True

    def rozlicz_stop(self, id_gracza):
        g = self.gracze[id_gracza]
        g.pominiete_tury = self.ile_stopow - 1
        self.ile_stopow = 0
        self.nastepny_gracz()
        return True

    def dobierz_z_talii(self, id_gracza):
        g = self.gracze[id_gracza]
        nowa_karta = self.pobierz_karte()
        if nowa_karta:
            g.dobierz_karte(nowa_karta)
        self.nastepny_gracz()
        return True

    def zglos_brak_uno(self, id_celu):
        g = self.gracze[id_celu]
        if len(g.reka) == 1 and not g.zglasza_uno:
            for _ in range(2):
                nowa_karta = self.pobierz_karte()
                if nowa_karta:
                    g.dobierz_karte(nowa_karta)
            return True
        return False


class srodowisko_uno:
    def __init__(self, liczba_graczy, max_graczy=5, nowa_gra=True):
        self.liczba_graczy = liczba_graczy
        self.max_graczy = max_graczy
        self.silnik = gra(liczba_graczy, nowa_gra)

    def _karta_na_indeks(self, k):
        if k.kolor is None:
            if k.wartosc == 'zmiana_koloru': return 52
            if k.wartosc == '+4': return 53
        kolory = ['czerwony', 'zielony', 'niebieski', 'zolty']
        wartosci = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'stop', 'zmiana_kierunku', '+2']
        baza = kolory.index(k.kolor) * 13
        offset = wartosci.index(k.wartosc)
        return baza + offset

    def _akcje_z_karty(self, k):
        if k.kolor is None:
            if k.wartosc == 'zmiana_koloru': return [52, 53, 54, 55]
            if k.wartosc == '+4': return [56, 57, 58, 59]
        return [self._karta_na_indeks(k)]

    def pobierz_stan(self, id_gracza):
        stan = []
        g = self.silnik.gracze[id_gracza]

        reka_wektor = [0] * 54
        for k in g.reka:
            idx = self._karta_na_indeks(k)
            reka_wektor[idx] += 1
        stan.extend(reka_wektor)

        stos_wektor = [0] * 54
        if self.silnik.stos:
            idx = self._karta_na_indeks(self.silnik.stos[-1])
            stos_wektor[idx] = 1
        stan.extend(stos_wektor)

        kolory = ['czerwony', 'zielony', 'niebieski', 'zolty']
        kolor_wektor = [0] * 4
        if self.silnik.aktualny_kolor in kolory:
            kolor_wektor[kolory.index(self.silnik.aktualny_kolor)] = 1
        stan.extend(kolor_wektor)

        stan.append(self.silnik.aktualna_kara)
        stan.append(self.silnik.kierunek)
        stan.append(1 if self.silnik.aktywne_combo else 0)
        stan.append(self.silnik.ile_stopow)

        historia_wektor = [0] * 54
        for k in self.silnik.wyrzucone_karty:
            idx = self._karta_na_indeks(k)
            historia_wektor[idx] += 1
        stan.extend(historia_wektor)

        # Dopasowanie stanu do MAX_GRACZY - puste miejsca wypełniane zerami
        for i in range(1, self.max_graczy):
            if i < self.liczba_graczy:
                idx_przeciwnika = (id_gracza + i) % self.liczba_graczy
                przeciwnik = self.silnik.gracze[idx_przeciwnika]
                stan.append(len(przeciwnik.reka))
                stan.append(1 if przeciwnik.zglasza_uno else 0)
                stan.append(przeciwnik.pominiete_tury)
            else:
                stan.extend([0, 0, 0])

        return stan

    def pobierz_maske_akcji(self, id_gracza):
        maska = [0] * (63 + self.max_graczy)
        g = self.silnik.gracze[id_gracza]
        ma_ruch = False

        if self.silnik.aktywne_combo is not None:
            for k in g.reka:
                if k.wartosc == self.silnik.aktywne_combo or (
                        self.silnik.aktywne_combo in ['+2', '+4'] and k.wartosc in ['+2', '+4']):
                    for a in self._akcje_z_karty(k): maska[a] = 1
            maska[62] = 1

            if len(g.reka) <= 2 and not g.zglasza_uno:
                maska[61] = 1
            for i in range(self.liczba_graczy):
                if i != id_gracza:
                    cel = self.silnik.gracze[i]
                    if len(cel.reka) == 1 and not cel.zglasza_uno:
                        idx_akcji = 63 + ((i - id_gracza) % self.liczba_graczy)
                        maska[idx_akcji] = 1
            return maska

        if self.silnik.aktualna_kara > 0:
            for k in g.reka:
                if k.wartosc in ['+2', '+4']:
                    for a in self._akcje_z_karty(k):
                        maska[a] = 1
                        ma_ruch = True
            if not ma_ruch:
                maska[60] = 1
            return maska

        if self.silnik.ile_stopow > 0:
            for k in g.reka:
                if k.wartosc == 'stop':
                    for a in self._akcje_z_karty(k):
                        maska[a] = 1
                        ma_ruch = True
            if not ma_ruch:
                maska[60] = 1
            return maska

        for k in g.reka:
            if self.silnik.waliduj_ruch(k):
                for a in self._akcje_z_karty(k):
                    maska[a] = 1
                    ma_ruch = True

        if not ma_ruch:
            maska[60] = 1

        if len(g.reka) <= 2 and not g.zglasza_uno:
            maska[61] = 1

        for i in range(self.liczba_graczy):
            if i != id_gracza:
                cel = self.silnik.gracze[i]
                if len(cel.reka) == 1 and not cel.zglasza_uno:
                    idx_akcji = 63 + ((i - id_gracza) % self.liczba_graczy)
                    maska[idx_akcji] = 1

        return maska

    def oblicz_nagrode_koncowa(self, miejsce):
        if miejsce == self.liczba_graczy: return -2000
        if self.liczba_graczy > 2: return -1000 * miejsce + 3000
        return 2000

    def resetuj(self):
        self.silnik = gra(self.liczba_graczy, True)
        return self.pobierz_stan(self.silnik.aktualny_gracz)

    def _znajdz_indeks_karty(self, id_gracza, id_typu_karty):
        g = self.silnik.gracze[id_gracza]
        for i, k in enumerate(g.reka):
            if self._karta_na_indeks(k) == id_typu_karty: return i
        return -1

    def _dekoduj_akcje(self, id_gracza, numer_akcji):
        if numer_akcji < 52:
            return 'zagraj', self._znajdz_indeks_karty(id_gracza, numer_akcji), None, None
        elif numer_akcji < 56:
            kolory = ['czerwony', 'zielony', 'niebieski', 'zolty']
            return 'zagraj', self._znajdz_indeks_karty(id_gracza, 52), kolory[numer_akcji - 52], None
        elif numer_akcji < 60:
            kolory = ['czerwony', 'zielony', 'niebieski', 'zolty']
            return 'zagraj', self._znajdz_indeks_karty(id_gracza, 53), kolory[numer_akcji - 56], None
        elif numer_akcji == 60:
            return 'pass_lub_dobierz', None, None, None
        elif numer_akcji == 61:
            return 'krzycz_uno', None, None, None
        elif numer_akcji == 62:
            return 'zakoncz_ture', None, None, None
        elif numer_akcji < 63 + self.max_graczy:
            odleglosc = numer_akcji - 63
            if odleglosc < self.liczba_graczy:
                id_celu = (id_gracza + odleglosc) % self.liczba_graczy
                return 'zglos_brak_uno', None, None, id_celu
        return None, None, None, None

    def wykonaj_krok(self, id_gracza, numer_akcji):
        nagroda = -2
        typ_akcji, indeks_karty, wybrany_kolor, id_celu = self._dekoduj_akcje(id_gracza, numer_akcji)

        if typ_akcji == 'zagraj':
            karta_zagrana = self.silnik.gracze[id_gracza].reka[indeks_karty]
            wiadomosc = f"Gracz {id_gracza} zagrywa: {karta_zagrana}"
            if wybrany_kolor:
                wiadomosc += f" (wybiera kolor: {wybrany_kolor})"
            self.silnik.dodaj_log(wiadomosc)
            self.silnik.zagraj_karte(id_gracza, indeks_karty, wybrany_kolor)
            nagroda += 1
        elif typ_akcji == 'pass_lub_dobierz':
            if self.silnik.aktualna_kara > 0:
                self.silnik.dodaj_log(f"Gracz {id_gracza} pobiera kare: {self.silnik.aktualna_kara} kart")
                self.silnik.rozlicz_kare(id_gracza)
                nagroda -= 5
            elif self.silnik.ile_stopow > 0:
                self.silnik.dodaj_log(f"Gracz {id_gracza} stoi w kolejce (blokada)")
                self.silnik.rozlicz_stop(id_gracza)
            else:
                self.silnik.dodaj_log(f"Gracz {id_gracza} dobiera karte z talii")
                self.silnik.dobierz_z_talii(id_gracza)
                nagroda -= 2
        elif typ_akcji == 'zakoncz_ture':
            self.silnik.dodaj_log(f"Gracz {id_gracza} konczy ture")
            self.silnik.zakoncz_ture(id_gracza)
        elif typ_akcji == 'krzycz_uno':
            self.silnik.dodaj_log(f"Gracz {id_gracza} krzyczy UNO!")
            self.silnik.krzycz_uno(id_gracza)
            nagroda += 1
        elif typ_akcji == 'zglos_brak_uno':
            self.silnik.dodaj_log(f"Gracz {id_gracza} zglasza brak UNO u gracza {id_celu}")
            self.silnik.zglos_brak_uno(id_celu)
            nagroda += 2

        czy_koniec = False
        if len(self.silnik.ranking) == 1:
            if id_gracza == self.silnik.ranking[0]:
                nagroda += 2000
                self.silnik.dodaj_log(f"!!! Gracz {id_gracza} WYGRYWA GRE !!!")
            czy_koniec = True

        return self.pobierz_stan(self.silnik.aktualny_gracz), nagroda, czy_koniec