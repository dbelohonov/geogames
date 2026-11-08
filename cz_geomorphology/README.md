# Geomorfologie Česka ⛰️

Učící hra na **geomorfologické členění České republiky** podle tematického
atlasu Pedagogické fakulty MU. Interaktivní vektorová mapa se třemi režimy
(stejně jako hra Okresy v Česku) a třemi úrovněmi členění:

| Úroveň | Počet útvarů | Délka kvízu |
|---|---|---|
| **Provincie** | 4 (Česká vysočina, Středoevropská nížina, Západní Karpaty, Západopanonská pánev) | 4 otázky |
| **Soustavy** | 10 (Šumavská, Poberounská, Krušnohorská, Krkonošsko-jesenická, Českomoravská, Česká tabule, Středopolské nížiny, Vněkarpatské sníženiny, Vnější Západní Karpaty, Vídeňská pánev) | 10 otázek |
| **Podsoustavy** | 27 (Krušnohorská hornatina, Brdská podsoustava, Jesenická podsoustava, Jihomoravské Karpaty, Středomoravské Karpaty …) | 10 otázek |

| Režim | Jak hraje |
|---|---|
| **Prozkoumat** | najedeš myší na útvar → zobrazí se název + nadřazená jednotka (u provincií počet soustav); přepínačem „ukázat všechny názvy“ si mapu prohlédneš celou |
| **Klikací kvíz** | hra vypíše název útvaru, ty na něj **klikneš** v mapě; volitelná nápověda = nadřazená jednotka (provincie u soustav, soustava u podsoustav) |
| **Psaný kvíz** | hra **zvýrazní útvar barvou**, ty **napíšeš** jeho název z klávesnice; **diakritika je volitelná** a slovotvorné přípony jsou povolné v obou verzích („Krušnohorská hornatina“ i „krusnohorska hornatina“, „Českoleská podsoustava“ i staré „Českoleská oblast“) |

Skóre se počítá průběžně a nejlepší výsledek se ukládá do `localStorage`
(zvlášť pro každou úroveň a režim).

## Terminologie

Atlas (2017) používá starší názvy úrovní — *subprovincie* a *oblast*.
Hra používá současné názvy: **soustava** (≈ subprovincie) a **podsoustava**
(≈ oblast). U jednotek, jejichž vlastní jméno končí slovem „oblast“,
je jméno přejmenováno („Českoleská oblast“ → „Českoleská podsoustava“,
„Brdská oblast“ → „Brdská podsoustava“ …); ostatní přípony se nemění
(*hornatina*, *vrchovina*, *pahorkatina*, *tabule*, *podhůří*, *Karpaty*,
*pánve*, *nížiny*). Staré jméno je v psaném kvízu přijímáno jako platná
odpověď, ale nikdy se nezobrazuje.

**Jihomoravské Karpaty** (Mikulovská vrchovina, Pavlovské vrchy) kreslí atlas
jako ostrůvek barvy Vnějších Západních Karpat mezi Vněkarpatskou sníženinou,
Vídeňskou pánví a rakouskou hranicí — ve vektorové vrstvě je to samostatný
uzavřený podobrys výplňové cesty, ne čára uvnitř soustavy. Hra ho proto bere
jako samostatný prstenec: vlastní klikací podsoustava i součást soustavy
a provincie. Podle geomorfologického členění (Demek–Mackovčin; srov.
lokalizační mapy „Vnější Západní Karpaty“, Daniel Baránek, CC BY-SA 3.0)
tvoří jihomoravskou část celku ještě Milovická pahorkatina jihozápadně od
Pálavy — tu ale atlas vybarvuje jako součást předhlubně (Vněkarpatské
sníženiny), a hra se drží atlasu.

## Spuštění

Hra je čistě statická (HTML + CSS + vanilla JS), žádný build ani server není
nutný — stačí otevřít `index.html` v prohlížeči. Pokud chceš servírovat
přes HTTP (např. kvůli iframe v katalogu):

```bash
cd cz_geomorphology
python3 -m http.server 8766
# → http://localhost:8766
```

## Struktura

```
cz_geomorphology/
├── index.html               # stránka hry (panel + mapa + přepínač úrovní)
├── css/style.css            # styly (světlý i tmavý režim)
├── js/
│   ├── data.js              # GENEROVANÉ: SVG cesty + popisky 40 útvarů
│   ├── normalize.js         # porovnávání odpovědí bez ohledu na diakritiku
│   └── game.js              # logika: úrovně, režimy, kvízy, skóre, feedback
├── data/geomorfologie.svg   # zdrojová vektorová mapa (atlas MU)
├── images/Geomorfologie_CR.jpg # referenční mapa s názvy (atlas MU) — odkaz v panelu
└── scripts/build_data.py    # generátor js/data.js ze SVG
```

## Odkud jsou data

- Vektorová mapa geomorfologického členění:
  [Česká republika – Tematický atlas](https://is.muni.cz/do/rect/el/estud/pedf/js17/cesko_atlas/web/pages/02-geomorfologie.html),
  Pedagogická fakulta Masarykovy univerzity (Mgr. Bc. Mariana Hájková,
  RNDr. Hana Svobodová, Ph.D.), © 2017 Masarykova univerzita —
  vrstva `pics/komplet/02_geomorfologie.svg`.
- Stejnojmenná rastrová mapa s popisky (`02-geomorfologie.jpg`) slouží jen
  jako referenční pomůcka (odkaz „📷 Referenční mapa“ v panelu).

## Jak funguje generátor

`js/data.js` se negeneruje ručně. Zdrojové SVG z atlasu obsahuje skupiny
`<g id="p_*">` (provincie, s obrysovou `<path>`), vnořené `<g id="sbp_*">`
(soustavy, s výplňovou `<path>`) a uvnitř nich šedé čáry = hranice
podsoustav + popisky oblastí (rotované, víceřádkové). Skript:

```bash
python3 -I scripts/build_data.py
```

1. převezme cesty provincií a soustav **beze změny** (SVG je už v cílových
   pixelových souřadnicích — žádná projekce ani zjednodušování),
2. popisky umístí metodou „pole of inaccessibility“ (nejvnitřnější bod
   na hrubém rastru, dvouprůchodová chamfer vzdálenostní transformace) —
   na rozdíl od těžiště zaručeně uvnitř i u úzkých zahnutých útvarů
   (Krkonošsko-jesenická soustava); u několika sousedících útvarů je
   hledání omezené (`LABEL_CLAMP`), aby se popisky nepřekrývaly,
3. **podsoustavy rekonstruuje planárním dělením**: šedé čáry jsou otevřené
   polyliny (včetně 6px „zářezů“ a T-spojů), jejich konce se přichytí
   k nejbližším vrcholkům obrysu či jiné čáry, úseky mezi uzly se zjednoduší
   RDP a stěny se vysbírají tak, že každá čára postupně rozpůlí stěnu,
   v níž má oba konce (face = oblouk obrysu + čára). Kontrola: počet stěn
   = počet popisků a součet ploch stěn = plocha soustavy. Uzavřené podobrysy
   výplňové cesty jsou exklávy: dostanou vlastní stěnu, pokud je atlas
   popisuje (Mikulovský výběžek = Jihomoravské Karpaty), jinak se přilejí
   k nejbližší stěně (Frýdlantský výběžek Středopolských nížin),
4. spáruje stěny s popisky (kotva textu, střed řádky, řádka pod textem —
   atlas někdy sází popisek *nad* malý útvar, např. Krkonošsko-jesenické
   podhůří), přejmenuje „… oblast“ → „… podsoustava“ a vypíše
   `window.GEOMORPH = {provincie, soustavy, podsoustavy}`.

## Poznámka k úrovni provincií

Obrysy provincií přebírá skript z obrysových cest SVG (`fill=none`),
které v atlasu kreslí vnější hranici každé provincie přes všechny její
soustavy — vnitřní dělicí čáry tak v úrovni „Provincie“ nejsou vidět.
