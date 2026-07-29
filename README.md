# AI Mouse Lab v0.6.0

Eén lokale Windows-hub voor het opbouwen van een persoonlijk muisprofiel en een blinde mens-versus-profielbenchmark.

## Hoofdflow

1. Neem Aim Lab-sessies op in de vaste virtuele arena van 1920 × 1080.
2. Bouw het masterprofiel opnieuw.
3. Open **Benchmark**.
4. Kies met de slider 10 tot 100 targets.
5. Speel zelf de targetreeks.
6. Bekijk A en B direct side-by-side op dezelfde Benchmark-pagina.
7. A wordt paars weergegeven en B groen; beide replays lopen synchroon.
8. Upload alleen `A.json` en `B.json` voor de blinde beoordeling.
9. Open `private_answer.json` pas na de keuze.

## v0.6.0

- vaste virtuele arena van 1920 × 1080 voor Aim Lab en Benchmark
- automatische schaal naar het beschikbare venster
- target-slider van 10 tot 100 targets
- Benchmark setup, run en replay in één hoofdflow
- side-by-side replay met gedeelde bediening
- persoonlijkere generator met begrensde bochtigheid, overshoot en fouten
- één consistente sessiestijl per gegenereerde benchmark
- minder extreme zigzags en minder overdreven slechte routes

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
- heatmaps of video-export
- neural network of diffusionmodel
