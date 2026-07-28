# AI Mouse Lab v0.3.0

Eén lokale Windows-hub met tabbladen voor Dashboard, Free Record, Aim Lab, Build Profile, Benchmark, Results, Profiles en Settings.

## Kernverbeteringen

- Volledige Aim Lab-route per target in één coördinatenstelsel
- Click down/up, reaction time, first entry, click delay en hold
- Misses worden bewaard in plaats van weggefilterd
- Smoothing voordat snelheid, acceleratie en jerk worden berekend
- Overshoot, entries, exits, correcties en path efficiency
- Transparante profielkwaliteit op basis van dekking, routediepte en contextvariatie
- Reproduceerbare benchmarkplannen met vaste seed
- Kernlogica opgesplitst in modules en voorzien van tests

## Starten

Dubbelklik `Start AI Mouse Lab.bat`.

## Testen

```bat
python -m unittest discover -s tests -v
```

## Bewust nog niet aanwezig

- externe muisbesturing
- cloudopslag
- automatische mens/AI-classifier
- custom image zone editor

De volgende Core-stap is de volledige menselijke benchmarkrunner en blinde A/B-export.
