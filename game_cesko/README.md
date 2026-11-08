# Okresy v Česku 🗺️

Učící hra na **okresy České republiky** (77 okresů včetně Prahy).
Interaktivní vektorová mapa se dvěma kvízovými režimy:

| Režim | Jak hraje |
|---|---|
| **Prozkoumat** | najedeš myší na okres → zobrazí se název + kraj; přepínačem „ukázat všechny názvy“ si mapu prohlédneš celou |
| **Klikací kvíz** | hra vypíše název okresu (10 náhodných), ty na něj **klikneš** v mapě; volitelná nápověda = kraj |
| **Psaný kvíz** | hra **zvýrazní okres barvou**, ty **napíšeš** jeho název z klávesnice; **diakritika je volitelná** („Brno-město“ i „brno mesto“ platí stejně) |

Každý kvíz má 10 otázek náhodně z 77 okresů, skóre se počítá průběžně
a nejlepší výsledek se ukládá do `localStorage`.

## Spuštění

Hra je čistě statická (HTML + CSS + vanilla JS), žádný build ani server není
nutný — stačí otevřít `index.html` v prohlížeči. Pokud chceš servírovat
přes HTTP (např. kvůli iframe v katalogu):

```bash
cd game_cesko
python3 -m http.server 8765
# → http://localhost:8765
```

## Struktura

```
game_cesko/
├── index.html            # stránka hry (panel + mapa)
├── css/style.css         # styly (světlý i tmavý režim)
├── js/
│   ├── data.js           # GENEROVANÉ: SVG cesty + metadata 77 okresů
│   ├── normalize.js      # porovnávání odpovědí bez ohledu na diakritiku
│   └── game.js           # logika: režimy, kvízy, skóre, feedback
├── data/okresy.geojson   # zdrojová hranice okresů (EPSG:4326)
├── images/Okresy_CR.png  # referenční mapa s názvy (Wikipedia) — odkaz v panelu
└── scripts/build_data.py # generátor js/data.js z geojsonu
```

## Odkud jsou data

- Hranice okresů: [`padytest/geojson-okresy`](https://github.com/padytest/geojson-okresy)
  (`okresy.geojson`, 77 polygonů, souřadnice WGS84).
- Referenční obrázek s popisky: Wikipedia,
  [*Okresy v Česku*](https://cs.wikipedia.org/wiki/Okresy_v_%C4%8Cesku).

## Přegenerování mapy

`js/data.js` se negeneruje ručně. Po výměně `data/okresy.geojson`:

```bash
python3 -I scripts/build_data.py
```

Skript zjednoduší polygony (Ramer–Douglas–Peucker, ~1 px tolerance),
naprojektuje je do SVG souřadnic (ekvidistantní projekce s korekcí šířky
≈ cos 49,8°) a spočítá těžiště pro popisky. Výstup: ~120 kB, ~7 900 bodů.

## Poznámka k „klikatelnosti“

Původní PNG z Wikipedie je plochý obrázek s vypálenými názvy — prohlížeč z něj
nepozná, na který okres jsi klikl, a popisky by prozrazovaly odpovědi.
Proto hra kreslí vlastní vektorovou mapu ze skutečných hranic (SVG `<path>`
pro každý okres = samostatný klikací prvek) a PNG zůstává jen jako
referenční pomůcka k nahlédnutí.
