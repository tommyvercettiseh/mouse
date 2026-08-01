# AI Mouse Lab v0.12.0

Lokale Windows-app voor het opnemen, modelleren en vergelijken van persoonlijke targetgerichte muisbewegingen.

## Hoofdflow

1. Neem een Aim Lab-sessie op in de vaste arena van 1920 × 1080.
2. Gebruik **Normale opname** voor profieldata of **Detectietest** voor technische controles.
3. Klik **Build Profile**.
4. Klik **Test nieuwste opname A/B** voor één directe vergelijking.
5. Open **Heatmap** om de nieuwste echte sessie meerdere keren te simuleren.
6. Kies 10 tot 500 runs en exporteer alle runs naar één `heatmap_runs.json`.

A gebruikt bij een A/B-test de nieuwste echte sessie. Gegenereerde runs gebruiken exact dezelfde starts, targets en targetgroottes met jouw persoonlijke profiel.

## Modelkwaliteit in v0.12.0

- route-templates krijgen een kwaliteitsscore en extreme vormen worden niet standaard hergebruikt
- afstand, richting en targetgrootte sturen timing, overshoot, correcties en misklikkans
- template-routes tellen click delay niet langer dubbel
- herhaalde stilstand en microbewegingen worden uit gegenereerde routes opgeschoond
- sample-intervallen zijn niet meer mechanisch gelijkmatig
- positieve overshoots gebruiken hun eigen persoonlijke verdeling, inclusief zeldzame grotere uitschieters
- approach-correcties negeren lage snelheid, microjitter en onbetrouwbare bijna-180° flips
- approach-metrics worden nu onderdeel van het persoonlijke profiel

Na deze update moet het bestaande profiel opnieuw worden opgebouwd via **Build Profile**, zodat de nieuwe context-, overshoot- en templatekwaliteitsvelden beschikbaar zijn.

## Actieve architectuur

- `app.py` — klein en stabiel startpunt
- `ai_mouse_lab/application.py` — applicatieshell, logging en foutafhandeling
- `ai_mouse_lab/ui_aim.py` — Aim Lab-opname, profielbouw en A/B-start
- `ai_mouse_lab/ui_replay.py` — doorlopende replay en klikvisualisatie
- `ai_mouse_lab/ui_heatmap.py` — herhaalde simulaties, route-overlay en mapknop
- `ai_mouse_lab/heatmap_flow.py` — nieuwste sessie naar herhaalbare multi-run-export
- `ai_mouse_lab/schema.py` — canoniek JSON-contract
- `ai_mouse_lab/models.py` — normalisatie en replayhelpers
- `ai_mouse_lab/metrics.py` — route-, klik-, overshoot- en bewegingsmetingen
- `ai_mouse_lab/braking.py` — rem- en targetbenaderingsanalyse
- `ai_mouse_lab/click_model.py` — persoonlijke mouse-downpositie en randpadding
- `ai_mouse_lab/profile_model.py` — contextprofiel, routevormen en kwaliteitsfiltering
- `ai_mouse_lab/generator.py` — persoonlijke contextuele routegenerator
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
- approach-correcties vóór target-entry
- entries, exits, correcties en misklikken
- persoonlijke klikafstand, randpadding en klikrichting
- genormaliseerde routevormen, waaronder terugkerende bochten, wiggles en overshoot-correcties

De klikpositie wordt vastgelegd op mouse-down. Beweging tijdens het vasthouden en loslaten telt niet mee als targetbeweging, acceleratie of overshoot.

Ruwe punten blijven bewaard, zodat metrics later opnieuw kunnen worden berekend. Routevormen worden genormaliseerd en op nieuwe afstanden en richtingen geprojecteerd. Zeldzame vreemde bewegingen blijven mogelijk, maar krijgen minder kans om een volledige generatie te domineren.

## Heatmap-export

De Heatmap-pagina gebruikt altijd de nieuwste voltooide Aim Lab-sessie als vaste targetplaylist. Alleen de generatorseed verschilt per run.

De export staat in:

```text
data/heatmaps/<datum-tijd>/heatmap_runs.json
```

Het bestand bevat het bronplan, het gekozen aantal runs en alle volledige trials met routepunten, clicks, misklikken en afgeleide metrics.

## Data

- `data/aim_lab` — menselijke Aim Lab-sessies
- `data/profiles` — persoonlijk masterprofiel
- `data/comparisons` — A/B-vergelijkingen
- `data/heatmaps` — herhaalde simulaties van de nieuwste sessie
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
