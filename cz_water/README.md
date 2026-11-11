# Vodstvo Česka 💧

Učící hra na **řeky České republiky** — 24 ptaných řek
(Vltava, Labe, Morava, Ohře, Sázava, Dyje, Jihlava, Svratka, Jizera, Lužnice,
Berounka, Odra, Otava, Opava, Radbuza, Chrudimka, Úhlava, Želivka, Mže,
Svitava, Úpa, Olše, Bečva, Vlára) v jedné interaktivní mapě se třemi režimy
(stejně jako hry Okresy v Česku, Geomorfologie Česka a Chráněná území
Česka). Kvízy se ptají 10 náhodných otázek napříč všemi 24 řekami a názvy
všude nesou svou kategorii („řeka Vltava“). Zbytek říční sítě je v mapě jen
jako slabý neinteraktivní kontext.

| Režim | Jak hraje |
|---|---|
| **Prozkoumat** | najedeš myší na řeku → zobrazí se název + kategorie; přepínačem „ukázat všechny názvy“ si mapu prohlédneš celou |
| **Klikací kvíz** | hra vypíše název řeky, ty na něj **klikneš** v mapě |
| **Psaný kvíz** | hra **zvýrazní řeku barvou**, ty **napíšeš** její název z klávesnice; **diakritika je volitelná** a předpona kategorie také („Vltava“ i „řeka Vltava“ platí stejně) |

Mapa kreslí řeky jako tenké linky na podkresu siluety republiky; u řek
zachytává kliky neviditelná široká „trubice“ kolem linky, aby se i tenký tok
dal trefit. Skóre se počítá průběžně a nejlepší výsledek se ukládá do
`localStorage` (zvlášť pro každý režim).

## Spuštění

Hra je čistě statická (HTML + CSS + vanilla JS), žádný build ani server není
nutný — stačí otevřít `index.html` v prohlížeči. Pokud chceš servírovat
přes HTTP (např. kvůli iframe v katalogu), spusť server z kořene repozitáře:

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
│   ├── data.js                     # GENEROVANÉ: silueta + linky řek
│   ├── normalize.js                # porovnávání odpovědí bez ohledu na diakritiku
│   └── game.js                     # logika: režimy, kvízy, skóre, feedback
├── data/
│   ├── 07-vodstvo.svg              # zdrojová vektorová mapa vodstva (atlas MU) — silueta
│   └── osm_rivers.json             # GENEROVANÉ: řeky z OSM promítnuté do souřadnic atlasu
└── scripts/
    ├── extract_osm.py              # shapefile OSM → data/osm_rivers.json (potřebuje images/)
    └── build_data.py               # atlas SVG + osm_rivers.json → js/data.js
```

## Odkud jsou data

- **Řeky a říční síť na pozadí**: shapefile vodstva ČR z OpenStreetMap
  (HOT export `images/hotosm_cze_waterways_osm_shp/`, snapshot 2026-11-03;
  © přispěvatelé OpenStreetMap, licence ODbL). Složka je neverzionovaná
  (kořenový `.gitignore`), promítnutý výsledek je uložený
  v `data/osm_rivers.json`. Z liniové vrstvy se vybírají segmenty 24 ptaných
  řek podle jména včetně jazykových a pohraničních variant (Thaya/Dyje,
  Olza/Olše, Eger/Ohře…), pramenné toky Vltavy (Teplá a Studená Vltava)
  a obě zdrojnice Bečvy; stejnojmenné potoky z jiných povodí (např. „Bečva“
  u Bohumína, „Lužnice“ v Krušných horách) se zahazují. Kontext na pozadí
  tvoří všechny zbývající toky `waterway=river`.
- **Silueta státu**: `data/07-vodstvo.svg` — list „Vodstvo“
  z webu *Česká republika – tematický atlas* (Masarykova univerzita, PedF,
  J. Svobodova; is.muni.cz, staženo 2025-11-09).

## Jak funguje generátor

`js/data.js` se negeneruje ručně, ale ve dvou krocích:

```bash
python3 -I scripts/extract_osm.py   # jen pokud měníš shapefile (potřebuje images/)
python3 -I scripts/build_data.py
```

**`extract_osm.py`** (shapefile → `data/osm_rivers.json`):

1. z DBF/SHP přečte segmenty ptaných řek a kontextové sítě,
2. sešije segmenty sdílející uzly do souvislých linií a přerušení toku
   v nádržích (OSM řeku přes hladinu nekreslí) přemostí rovnou čarou —
   řeka tak teče souvisle i přes hladiny přehrad,
3. napasuje kubické zobrazení zeměpisných souřadnic do viewBox atlasu:
   startuje kvadratickým fitem na centroidech 18 nádrží, které kreslí atlas
   i OSM, a doladí ho metodou ICP (promítne body OSM řek a přichytí je na
   atlasové linie těchže řek); výsledná odchylka je pod ~1 jednotkou viewBoxu
   (≈ 1 km) a hlídají ji asserty,
4. promítnuté linie ořízne siluetou státu (s tolerancí pro generalizaci
   hranice, aby pohraniční toky nevznikaly přerušovaně) a zjednoduší
   Ramer–Douglas–Peuckerem.

**`build_data.py`** (atlas + JSON → `js/data.js`): rozparsová SVG siluetu
(včetně vnořených transformací), poskládá záznamy řek
z `osm_rivers.json` (včetně kotev popisků) a vše přepočte do viewBox
517 × 367. Popisky řek z atlasu mají ručně zvolené kotvy (laděno podle
snímku s odhalenými názvy), nových 14 řek se kotví automaticky vedle toku
s možností ručního přepsání v `LABELS_VB`.

## Poznámky k mapě

- Řeky nesou plnou detailnost OSM (meandry, soutoky) — na rozdíl od
  generalizované kresby atlasu; silueta zůstává z atlasu.
- Toky končí přesně na státní hranici (ořez siluetou), pohraniční řeky
  (Odra, Olše, Morava, Dyje, Lužnice…) tak kopírují obrys státu.
