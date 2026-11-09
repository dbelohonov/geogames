# Vodstvo Česka 💧

Učící hra na **řeky a přehradní nádrže České republiky** — 10 ptaných řek
(Vltava, Labe, Dyje, Ohře, Morava, Berounka, Sázava, Jihlava, Mže, Odra)
a 24 vodních ploch ze zdrojové mapy vodstva (soustava Nové Mlýny hraje
jako jedno území; šest nádrží, které atlas nekreslí — Fláje, Přísečnice,
Hněvkovice, Římov, Březová a Josefov Důl — je umístěno ručně na správném
toku). Řeky i nádrže hrají **dohromady** v jedné interaktivní mapě
se třemi režimy (stejně jako hry Okresy v Česku, Geomorfologie Česka
a Chráněná území Česka) — bez přepínače kategorií. Kvízy se ptají
10 náhodných otázek napříč všemi 34 územími a názvy všude nesou svou
kategorii („řeka Vltava“, „VN Lipno“). Ostatní řeky atlasu jsou v mapě
jen jako slabý neinteraktivní kontext.

| Režim | Jak hraje |
|---|---|
| **Prozkoumat** | najedeš myší na řeku nebo nádrž → zobrazí se název + kategorie; přepínačem „ukázat všechny názvy“ si mapu prohlédneš celou |
| **Klikací kvíz** | hra vypíše název území (včetně zkratky kategorie), ty na něj **klikneš** v mapě |
| **Psaný kvíz** | hra **zvýrazní území barvou**, ty **napíšeš** jeho název z klávesnice; **diakritika je volitelná** a předpona kategorie také („Lipno“, „VN Lipno“ i „vodní nádrž Lipno“ platí stejně; u Švihova prochází i „Želivka“, u Nových Mlýnů i „Mušov“, „Věstonická“ a „Novomlýnská“) |

Mapa kreslí řeky jako tenké linky a nádrže jako vyplněné plochy na
podkresu siluety republiky; u řek zachytává kliky neviditelná široká
„trubice“ kolem linky, aby se i tenký tok dal trefit. Skóre se počítá
průběžně a nejlepší výsledek se ukládá do `localStorage` (zvlášť pro
každý režim).

## Spuštění

Hra je čistě statická (HTML + CSS + vanilla JS), žádný build ani server není
nutný — stačí otevřít `index.html` v prohlížeči. Pokud chceš servírovat
přes HTTP (např. kvůli iframe v katalogu), spusť server z kořene repozitáře —
jinak hra nedosáhne na sdílenou složku `../images/` s referenční mapou:

```bash
python3 -m http.server 8768
# → http://localhost:8768/cz_water/
```

## Struktura

```
cz_water/
├── index.html                      # stránka hry (panel + mapa)
├── css/style.css                   # styly (světlý i tmavý režim)
├── js/
│   ├── data.js                     # GENEROVANÉ: silueta + linky řek + plochy nádrží
│   ├── normalize.js                # porovnávání odpovědí bez ohledu na diakritiku
│   └── game.js                     # logika: režimy, kvízy, skóre, feedback
├── data/07-vodstvo.svg               # zdrojová vektorová mapa vodstva (atlas MU)
├── data/Czech_reservoirs_top_25.png  # starší rastrová reference (už jen pro srovnání)
└── scripts/build_data.py           # generátor js/data.js ze SVG
```

Referenční mapa s názvy leží mimo složku hry, ve sdílené
`../images/Czech_reservoirs_–_top_25.png` (v kořeni repozitáře,
neverzionováno — viz `.gitignore`); odkaz v panelu míří tam. Geometrie
hry ale pochází z vektorového atlasu (viz níže).

## Odkud jsou data

- Zdrojová mapa `07-vodstvo.svg`: list „Vodstvo“ z webu *Česká republika –
  tematický atlas* (Masarykova univerzita, PedF, J. Svobodova;
  is.muni.cz, staženo 2025-11-09). Vektorová mapa se siluetou státu,
  říční sítí, vodními plochami a popisky — geometrie hry z ní jde
  vytáhnout přímo, bez zpracování obrazu.
- Šest nádrží (Fláje, Přísečnice, Hněvkovice, Římov, Březová, Josefov
  Důl) atlas nekreslí; aby zůstal původně odsouhlasený seznam, mají
  v herní mapě ručně umístěnou mini-plochu na správném toku.

## Jak funguje generátor

`js/data.js` se negeneruje ručně:

```bash
python3 -I scripts/build_data.py
```

1. rozparsová SVG včetně vnořených transformací a podle barvy vrstev
   rozezná siluetu státu (zelená výplň), říční síť (modré tahy) a vodní
   plochy (modré výplně),
2. z říční sítě vybere deset ptaných řek (kontrola bboxem proti
   očekávání, aby se při změně zdroje nezamlčela chyba) a zbytek ponechá
   jako kontext,
3. vodní plochy spáruje s názvy podle polohy; slitou soustavu Nové Mlýny
   ponechá jako jedno území,
4. vše zjednoduší Ramer–Douglas–Peuckerem a přepočte do viewBox 517 × 367,
5. popisky umístí ručně zvolené kotvy (vedle toku / u nádrže), výsledek
   se kontroluje snímkem s odhalenými názvy.

## Poznámky k mapě

- Herní mapa přebírá geografii atlasu včetně jeho generalizace; drobné
  ruční úpravy (šest mini-nádrží) jsou stylizace v měřítku hry.
- Švihov se jmenuje i Želivka (podle řeky) a soustava Nové Mlýny má tři
  basény (Mušov, Věstonická, Novomlýnská) — psaný kvíz přijímá všechna
  tahle jména.
