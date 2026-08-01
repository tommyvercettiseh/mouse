# AI Mouse Lab v0.9.1

Lokale Windows-app voor het opnemen, modelleren en vergelijken van persoonlijke muisbewegingen.

## Hoofdflow

1. Neem een Aim Lab-sessie op in de vaste virtuele arena van 1920 × 1080.
2. Gebruik **Normale opname** voor profieldata of **Detectietest** voor technische controles.
3. Klik **Build Profile**.
4. Klik **Test nieuwste opname A/B**.
5. A gebruikt de laatste echte Aim Lab-opname; B gebruikt exact dezelfde targetplaylist en het persoonlijke profiel.
6. Results speelt alle targets automatisch achter elkaar af.

## Actieve architectuur

De launcher start `app.py`. Dat bestand laadt uitsluitend `app_v1.py`; de historische patchketen wordt niet meer uitgevoerd.

De actieve kern bestaat uit:

- `app_v1.py` — Free Record, Aim Lab, profielbediening en doorlopende A/B-replay
- `ai_mouse_lab/schema.py` — het enige canonieke JSON-contract en compatibiliteitsnormalisatie
- `ai_mouse_lab/models.py` — dunne replayhelpers boven op het schema
- `ai_mouse_lab/metrics.py` — route-, click-, overshoot- en bewegingsmetingen
- `ai_mouse_lab/braking.py` — robuuste rem- en targetbenaderingsanalyse
- `ai_mouse_lab/profile_model.py` — contexten, kwaliteitsfiltering en featurestatistieken
- `ai_mouse_lab/generator.py` — zelfstandige persoonlijke routegenerator
- `ai_mouse_lab/personal_model.py` — kleine publieke compatibiliteitslaag
- `ai_mouse_lab/comparison_flow.py` — laatste Aim Lab-opname naar A/B-comparison
- `ai_mouse_lab/storage.py` — atomaire lokale JSON-opslag

## Geregistreerde bewegingseigenschappen

Per target worden de volledige ruwe route, startpositie, targetpositie, targetgrootte, eindklik en alle misklikken opgeslagen. Daaruit worden onder meer berekend:

- reaction time, movement time, click delay en hold
- afstand, padlengte en route-efficiëntie
- pieksnelheid en tijdstip van pieksnelheid
- piekacceleratie, piekdeceleratie en jerk
- aanhoudende remstart, remafstand en remduur
- gemiddelde targetbenaderingssnelheid
- snelheid op 2×, 1× en 0,5× targetradius
- gemiddelde snelheid in de laatste 100 ms vóór de klik
- snelheid bij eerste target-entry en slowdown-ratio
- radiale en directionele overshoot
- entries, exits, correcties en misklikken

De ruwe punten blijven bewaard. Daardoor kan de afgeleide meetlogica later opnieuw worden berekend zonder een nieuwe opname.

## Data

- `data/aim_lab` — menselijke Aim Lab-sessies
- `data/profiles` — persoonlijk masterprofiel
- `data/comparisons` — A/B-vergelijkingen
- `data/recordings` — vrije cursoropnames

Bestaande lokale data wordt niet automatisch verwijderd. Oude lijstvormige punten en afwijkende velden worden bij het inlezen naar schema 7 genormaliseerd.

## Testen

```bat
python -m unittest discover -s tests -v
```

## Bewust nog niet

- externe muisbesturing
- image detection of click automation
- cloudopslag
- database of extra framework
- heatmaps of video-export
- automatische classifier

De versie blijft 0.9.1 totdat de volledige Windows-flow lokaal is bevestigd: Aim Lab → Build Profile → A/B → Alles afspelen.
