# Chráněná území Česka 🌿

Učící hra na **velkoplošná zvláště chráněná území České republiky** —
4 národní parky a 27 chráněných krajinných oblastí (stav 2025, včetně
nejnovější CHKO Soutok). Interaktivní vektorová mapa se třemi režimy
(stejně jako hry Okresy v Česku a Geomorfologie Česka) a dvěma kategoriemi:

| Kategorie | Počet území | Délka kvízu |
|---|---|---|
| **Národní parky** | 4 (Šumava, Krkonoše, České Švýcarsko, Podyjí) | 4 otázky |
| **CHKO** | 27 (Beskydy, Šumava, Jeseníky, Český ráj, Pálava, Soutok …) | 10 otázek |

| Režim | Jak hraje |
|---|---|
| **Prozkoumat** | najedeš myší na území → zobrazí se název + kategorie; přepínačem „ukázat všechny názvy“ si mapu prohlédneš celou |
| **Klikací kvíz** | hra vypíše název území zvolené kategorie, ty na něj **klikneš** v mapě |
| **Psaný kvíz** | hra **zvýrazní území barvou**, ty **napíšeš** jeho název z klávesnice; **diakritika je volitelná** a předpona kategorie také („Brdy“, „CHKO Brdy“ i „chráněná krajinná oblast Brdy“ platí stejně; u Krkonoš prochází i „Krkonošský NP“ a „KRNAP“) |

Mapa vždy kreslí obě kategorie (hnědě NP, zeleně CHKO — barvy zdrojové
mapy) na podkresu siluety republiky; přepínač kategorie určuje, na kterou
sadu se kvízy ptají. Druhá kategorie v kvízu zešedne a není klikací.
V režimu Prozkoumat jsou živé obě. Skóre se počítá průběžně a nejlepší
výsledek se ukládá do `localStorage` (zvlášť pro každou kategorii a režim).

## Spuštění

Hra je čistě statická (HTML + CSS + vanilla JS), žádný build ani server není
nutný — stačí otevřít `index.html` v prohlížeči. Pokud chceš servírovat
přes HTTP (např. kvůli iframe v katalogu), spusť server z kořene repozitáře —
jinak hra nedosáhne na sdílenou složku `../images/` s referenční mapou:

```bash
python3 -m http.server 8767
# → http://localhost:8767/cz_nature/
```

## Struktura

```
cz_nature/
├── index.html               # stránka hry (panel + mapa + přepínač kategorií)
├── css/style.css            # styly (světlý i tmavý režim)
├── js/
│   ├── data.js              # GENEROVANÉ: SVG cesty + popisky 31 území
│   ├── normalize.js         # porovnávání odpovědí bez ohledu na diakritiku
│   └── game.js              # logika: kategorie, režimy, kvízy, skóre, feedback
├── data/CR_VZCHU_2025.svg   # zdrojová vektorová mapa (velkoplošná ZCHÚ, 2025)
└── scripts/build_data.py    # generátor js/data.js ze SVG
```

Referenční mapa s názvy leží mimo složku hry, ve sdílené
`../images/CR_VZCHU_2025.svg` (v kořeni repozitáře, neverzionováno —
viz `.gitignore`); odkaz v panelu míří tam. Je to týž soubor jako
zdrojová mapa v `data/` — hra z něj data generuje, panel ho otevírá
k nahlédnutí i s původními popisky.

## Odkud jsou data

- Zdrojová vektorová mapa `CR_VZCHU_2025.svg` (export z Illustratoru,
  tři vrstvy: podkres republiky + NP, CHKO, popisky) byla do projektu
  přidána lokálně; zachycuje stav 2025 včetně CHKO Soutok.

## Jak funguje generátor

`js/data.js` se negeneruje ručně. Zdrojové SVG neobsahuje u tvarů žádná
jména — popisky jsou zvlášť ve vrstvě `Vrstva_6` a jejich kerningové
`tspan`y ztrácejí mezery („CHKOLitovelskéPomoraví“), takže texty nejsou
spolehlivý zdroj jmen. Názvy (včetně přijímaných variant pro psaný kvíz)
jsou proto v tabulkách ve skriptu a skript k nim tvary **páruje podle
polohy popisku**:

```bash
python3 -I scripts/build_data.py
```

1. vytáhne tvary: podkres republiky (šedý polygon), 4 NP (hnědé tvary
   z první vrstvy; legendové čtverečky pozná podle počtu vrcholů) a
   27 CHKO (zelené tvary z druhé vrstvy), duplicitní NP polygon ve
   vrstvě s popisky ignoruje,
2. spáruje popisek s tvarem váženým hlasováním zkušebních bodů podél
   celé textové řádky (body u začátku nápisu a na základní lince váží
   nejvíc — výtvarníci začínají popisek „svým“ územím, ale dlouhé názvy
   přetékají přes sousedy; řádky pod linkou chytí popisky sázené nad
   malým územím). Přiřazuje se iterativně: nejdřív jednoznačné páry
   (nejlepší skóre ≥ 2× druhé nejlepší), po jejich odebrání ze hry se
   přepočítají sporné — tak se vyřeší např. záměna Blanský les ↔
   Třeboňsko, kde jeden popisek končí nad sousedovým územím. Pár tvarů,
   jejichž popisek startuje daleko mimo (NP Šumava, NP České Švýcarsko),
   dopočítá nejbližší vzdáleností. Kontrola: párování musí vyjít 1:1,
3. geometrii přebírá **beze změny** (SVG je už v cílových souřadnicích),
   jen ji zjednoduší RDP (~0,2 px) a zachová `fill-rule: evenodd` —
   NP Krkonoše má tři enklávy jako díry a šest CHKO je vícedílných
   (Labské pískovce, Český ráj, Šumava, Český les, České středohoří,
   Soutok),
4. popisky umístí metodou „pole of inaccessibility“ (nejvnitřnější bod
   na hrubém rastru) — na rozdíl od těžiště zaručeně uvnitř i u
   úzkých či vícedílných útvarů,
5. vypíše `window.NATURE = {base, np, chko}`.

## Poznámky k mapě

- CHKO Šumava a Labské pískovce ve zdroji částečně překrývají „své“
  národní parky (vrstva CHKO je nad vrstvou NP). Hra kreslí NP **nad**
  CHKO, takže parky zůstávají vidět i klikatelné celé — stejně jako na
  oficiálních mapách.
- NP Šumava a CHKO Šumava jsou dvě různá území (park je jádrová oblast,
  CHKO ji obepíná); v kvízu je nikdy nepotkáš zároveň, protože kategorie
  se ptají zvlášť.
- Krkonoše se ve zdroji jmenují „Krkonošský NP“; hra jednotně zobrazuje
  „NP Krkonoše“, ale „Krkonošský NP“, „Krkonošský národní park“ i „KRNAP“
  v psaném kvízu přijímá.
