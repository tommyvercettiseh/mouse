# AI Mouse Lab v0.9.1

Lokale Windows-app voor het opnemen, modelleren en vergelijken van persoonlijke muisbewegingen.

## Hoofdflow

1. Neem een Aim Lab-sessie op in de vaste virtuele arena van 1920 × 1080.
2. Gebruik **Normale opname** voor trainingsdata of **Detectietest** voor technische controles.
3. Klik **Build Profile** om het persoonlijke masterprofiel opnieuw te bouwen.
4. Klik **Test nieuwste opname A/B**.
5. A gebruikt de laatste echte Aim Lab-opname; B gebruikt exact dezelfde targetplaylist en wordt gegenereerd met het persoonlijke profiel.
6. Results speelt alle targets automatisch achter elkaar af.

## Actieve architectuur

De applicatie start rechtstreeks via `app_clean.py`. De oude `v06` tot en met `v083` patchbestanden blijven alleen als historische rollbackbron in de repository en worden niet meer uitgevoerd.

De actieve kern bestaat uit:

- `app_clean.py` — UI, opnamebediening en replaycontroller
- `ai_mouse_lab/schema.py` — canoniek trial- en sessiecontract
- `ai_mouse_lab/models.py` — typed compatibiliteitsmodellen
- `ai_mouse_lab/comparison_flow.py` — laatste Aim Lab-opname naar A/B-comparison
- `ai_mouse_lab/personal_model.py` — profielbouw en persoonlijke generatie
- `ai_mouse_lab/profile_model.py` — contexten, kwaliteitsfiltering en featurestatistieken
- `ai_mouse_lab/metrics.py` — route-, click-, overshoot- en bewegingsmetingen
- `ai_mouse_lab/braking.py` — remgedrag en snelheid tijdens targetbenadering
- `ai_mouse_lab/storage.py` — lokale JSON-opslag

## Geregistreerde bewegingseigenschappen

- reaction time, movement time, click delay en hold
- afstand, padlengte en route-efficiëntie
- pieksnelheid en tijdstip van pieksnelheid
- piekacceleratie, piekdeceleratie en jerk
- echte remstart op basis van aanhoudende vertraging
- remafstand en remduur
- gemiddelde targetbenaderingssnelheid
- snelheid op 2×, 1× en 0,5× targetradius
- gemiddelde snelheid in de laatste 100 ms voor de klik
- snelheid bij eerste target-entry en slowdown-ratio
- radiale en directionele overshoot
- entries, exits, correcties en misklikken

## Data

- `data/aim_lab` — menselijke Aim Lab-sessies
- `data/profiles` — persoonlijk masterprofiel
- `data/comparisons` — A/B-vergelijkingen
- `data/recordings` — vrije opnames

Bestaande lokale data wordt niet automatisch verwijderd.

## Testen

```bat
python -m unittest discover -s tests -v
```

## Bewust nog niet

- externe muisbesturing
- cloudopslag
- database of extra framework
- heatmaps of video-export
- automatische classifier
