# AI Mouse Lab v0.4.0

Eén lokale Windows-hub voor Aim Lab-profielopbouw en een echte blinde mens-versus-profielbenchmark.

## Benchmarkflow

1. Bouw eerst je masterprofiel.
2. Open **Benchmark**.
3. Kies 20, 50 of 100 targets.
4. Klik zelf de volledige targetreeks.
5. De generator simuleert dezelfde targets met jouw werkelijke startposities.
6. De app exporteert `A.json` en `B.json` met exact hetzelfde schema.
7. Upload alleen A en B voor de blinde beoordeling.
8. Open `private_answer.json` pas nadat de keuze is gemaakt.

## Benchmarkmap

```text
data/benchmarks/<sessie>/
├── benchmark_plan.json
├── human_private.json
├── generated_private.json
├── A.json
├── B.json
├── private_answer.json
└── summary.json
```

## Testen

```bat
python -m unittest discover -s tests -v
```

## Bewust nog niet

- externe muisbesturing
- cloudopslag
- automatische classifier in de app
- custom image zone editor
