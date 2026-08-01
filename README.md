# AI Mouse Lab v0.10.0

Lokale Windows-app voor het opnemen, modelleren en vergelijken van persoonlijke targetgerichte muisbewegingen.

## Hoofdflow

1. Neem een Aim Lab-sessie op in de vaste arena van 1920 × 1080.
2. Gebruik **Normale opname** voor profieldata of **Detectietest** voor technische controles.
3. Klik **Build Profile**.
4. Klik **Test nieuwste opname A/B**.
5. A gebruikt de nieuwste echte sessie; B gebruikt dezelfde starts, targets en targetgroottes met jouw persoonlijke profiel.
6. Results speelt alle targets automatisch af en toont routes, mouse-downposities en misklikken.

## Actieve architectuur

- `app.py` — klein en stabiel startpunt
- `ai_mouse_lab/application.py` — applicatieshell, logging en foutafhandeling
- `ai_mouse_lab/ui_aim.py` — Aim Lab-opname, profielbouw en A/B-start
- `ai_mouse_lab/ui_replay.py` — doorlopende replay en klikvisualisatie
- `ai_mouse_lab/schema.py` — canoniek JSON-contract
- `ai_mouse_lab/models.py` — normalisatie en replayhelpers
- `ai_mouse_lab/metrics.py` — route-, klik-, overshoot- en bewegingsmetingen
- `ai_mouse_lab/braking.py` — rem- en targetbenaderingsanalyse
- `ai_mouse_lab/click_model.py` — persoonlijke mouse-downpositie en randpadding
- `ai_mouse_lab/profile_model.py` — profielbouw, routevormen en kwaliteitsfiltering
- `ai_mouse_lab/generator.py` — persoonlijke routegenerator
- `ai_mouse_lab/comparison_flow.py` — nieuwste sessie naar A/B-comparison
- `ai_mouse_lab/storage.py` — atomaire lokale JSON-opslag

De actieve code bevat geen patchketen, legacy-wrapper of Free Record-flow.

## Geregistreerde eigenschappen

- reaction time, movement time, click delay en hold
- afstand, padlengte en route-efficiëntie
- snelheid, acceleratie, deceleratie en jerk
- remstart, remafstand en remduur
- snelheden op 2×, 1× en 0,5× targetradius
- snelheid in de laatste 100 ms en bij eerste target-entry
- slowdown-ratio
- radiale en directionele overshoot
- entries, exits, correcties en misklikken
- persoonlijke klikafstand, randpadding en klikrichting
- genormaliseerde routevormen, waaronder terugkerende bochten, wiggles en overshoot-correcties

De klikpositie wordt vastgelegd op mouse-down. Beweging tijdens het vasthouden en loslaten telt niet mee als targetbeweging, acceleratie of overshoot.

Ruwe punten blijven bewaard, zodat metrics later opnieuw kunnen worden berekend. Routevormen worden genormaliseerd en op nieuwe afstanden en richtingen geprojecteerd; een eenmalige vreemde beweging wordt daardoor niet automatisch een vaste gewoonte.

## Data

- `data/aim_lab` — menselijke Aim Lab-sessies
- `data/profiles` — persoonlijk masterprofiel
- `data/comparisons` — A/B-vergelijkingen
- `logs/ai_mouse_lab.log` — onverwachte applicatiefouten

Bestaande lokale data wordt niet automatisch verwijderd. Oudere opnames worden bij het inlezen naar mouse-downsemantiek en het huidige schema genormaliseerd.

## Starten

Dubbelklik op:

```text
Start AI Mouse Lab.bat
```

De launcher installeert benodigdheden alleen wanneer ze ontbreken.

## Testen

```bat
python -m unittest discover -s tests -v
```

GitHub Actions voert dezelfde tests en een compile-check uit op Windows en Linux.

## Scope

Zie `PRODUCT.md` voor de vaste hoofdtaak en `ROADMAP.md` voor bewust uitgestelde functies.
