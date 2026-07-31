# AI Mouse Lab v0.7.0

Eén lokale Windows-hub voor het opbouwen van een persoonlijk muisprofiel en een blinde mens-versus-profielbenchmark.

## Hoofdflow

1. Neem Aim Lab-sessies op in de vaste virtuele arena van 1920 × 1080.
2. Kies **Normale opname** voor trainingsdata of **Detectietest** voor technische experimenten.
3. Bouw het masterprofiel opnieuw.
4. Open **Benchmark**, speel zelf en bekijk A en B synchroon op één arena.
5. Upload alleen `A.json` en `B.json` voor een blinde beoordeling.

## Persoonlijk contextmodel

Het profiel leert niet alleen algemene gemiddelden, maar verdeelt jouw gedrag over contexten op basis van:

- korte, middellange en lange bewegingen
- kleine, middelgrote en grote targets
- acht bewegingsrichtingen
- reactietijd, bewegingstijd en klikvertraging
- remstart, snelheid, versnelling en jerk
- overshoot, correcties, entries/exits en misklikken
- routevormen en klikpositie

Technische detectietests en onwaarschijnlijke recorderuitschieters worden niet gebruikt als normale trainingsdata. Het profiel bewaart aantallen en afwijsredenen zodat dit controleerbaar blijft.

## Datakwaliteit

Voor een sterk profiel zijn meerdere normale sessies nodig. Richtwaarde:

- 200–300 geaccepteerde targets
- meerdere sessies
- verschillende afstanden, richtingen en targetgroottes
- minimaal acht voorbeelden in de belangrijkste contexten

## Testen

```bat
python -m unittest discover -s tests -v
```

## Bewust nog niet

- externe muisbesturing
- cloudopslag
- automatische classifier
- heatmaps of video-export
- neural network of diffusionmodel
