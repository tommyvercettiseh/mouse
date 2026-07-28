# AI Mouse Lab

AI Mouse Lab is een lokale Windows-tool om eigen muisgedrag op te nemen, gericht te meten en visueel te vergelijken met een profielsimulatie.

## Eén centrale hub

De applicatie gebruikt één hoofdvenster met pagina's in de linkerzijbalk:

- Dashboard
- Free Record
- Aim Lab
- Build Profile
- Benchmark
- Results
- Profiles
- Settings

Er worden geen losse schermen of aparte Aim Lab-processen geopend.

## Starten

Dubbelklik op:

```text
Start AI Mouse Lab.bat
```

De launcher maakt automatisch een lokale `.venv`, installeert de dependencies en opent daarna de Windows-app.

## Huidige versie 0.1.0

### Free Record

- globale muisbewegingen opnemen;
- exacte timestamps;
- links-, rechts- en middenklikken;
- click down/up en klikduur;
- scroll-events;
- live teller voor events, klikken, scrolls en opnameduur;
- live cursorpositie;
- abstracte weergave van alle Windows-monitoren;
- kort vervagend spoor;
- lokale JSON-opslag.

### Aim Lab

- geïntegreerd in hetzelfde hoofdvenster;
- instelbaar op 20, 50 of 100 targets;
- gemengde targetgroottes;
- willekeurige posities;
- opslag van start, target, afstand, bewegingstijd, klikpositie en klikfout.

### Build Profile

- combineert Free Record en Aim Lab-data;
- berekent transparante statistieken;
- bewaart één lokaal `master_profile.json`;
- toont profielkwaliteit op basis van beschikbare data.

### Benchmark

- maakt een vaste targetreeks;
- maakt een visuele profielsimulatie zonder de echte Windows-muis te besturen;
- bewaart alle benchmarkdata lokaal;
- A/B blind-export en volledige menselijke benchmarkrunner worden de eerstvolgende kernuitbreiding.

## Lokale data

```text
data/
├── recordings/
├── aim_lab/
├── profiles/
└── benchmarks/
```

Deze mappen worden niet naar GitHub gepusht.

## Grenzen

- geen toetsenbordopname;
- geen screenshots;
- geen cloudopslag;
- geen externe muisbesturing;
- geen botfunctionaliteit;
- profielsimulatie blijft binnen de app en lokale JSON-data.

## Ontwikkelen

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```
