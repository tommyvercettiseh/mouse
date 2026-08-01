# AI Mouse Lab v0.9.4

Lokale Windows-app voor het opnemen, modelleren en vergelijken van persoonlijke muisbewegingen in een vaste Aim Lab-arena.

## Hoofdflow

1. Neem een Aim Lab-sessie op in 1920 × 1080.
2. Gebruik **Normale opname** voor profieldata of **Detectietest** voor technische controles.
3. Klik **Build Profile**.
4. Klik **Test nieuwste opname A/B**.
5. A gebruikt de laatste echte opname; B gebruikt dezelfde targets en jouw persoonlijke profiel.
6. Results speelt alle targets automatisch achter elkaar af.

## Productscope

Free Record is uit de actieve applicatie verwijderd. Globale cursorposities zijn niet betrouwbaar voor games met raw input, cursor-locking of onbeperkte cameradraai. Aim Lab blijft daarom de enige trainingsbron.

De actieve kern bestaat uit:

- `app.py` — actieve Aim Lab-interface
- `app_v1.py` — Aim Lab-, profiel- en replayimplementatie; oude Free Record-methodes zijn niet bereikbaar vanuit de actieve app
- `ai_mouse_lab/schema.py` — canoniek JSON-contract
- `ai_mouse_lab/metrics.py` — route-, click-, overshoot- en bewegingsmetingen
- `ai_mouse_lab/braking.py` — rem- en targetbenaderingsanalyse
- `ai_mouse_lab/click_model.py` — persoonlijke klikpositie binnen targets
- `ai_mouse_lab/profile_model.py` — profielbouw en kwaliteitsfiltering
- `ai_mouse_lab/generator.py` — persoonlijke routegenerator
- `ai_mouse_lab/comparison_flow.py` — laatste opname naar A/B-comparison
- `ai_mouse_lab/storage.py` — lokale JSON-opslag

## Geregistreerde eigenschappen

- reaction time, movement time, click delay en hold
- afstand, padlengte en route-efficiëntie
- snelheid, acceleratie, deceleratie en jerk
- remstart, remafstand en remduur
- targetbenaderingssnelheid en slowdown
- radiale en directionele overshoot
- entries, exits, correcties en misklikken
- persoonlijke klikafstand, randpadding en klikrichting

## Data

- `data/aim_lab` — menselijke Aim Lab-sessies
- `data/profiles` — persoonlijk masterprofiel
- `data/comparisons` — A/B-vergelijkingen

Bestaande lokale Free Record-bestanden worden niet automatisch verwijderd, maar worden niet gebruikt.

## Testen

```bat
python -m unittest discover -s tests -v
```

## Bewust nog niet

- raw-inputrecorder voor games
- externe muisbesturing
- image detection of click automation
- cloudopslag
- automatische classifier
