# Roadmap

## Nu — 0.10.0 stabiliteitsrelease

- één actieve applicatie zonder legacy-wrapper;
- Free Record-code volledig verwijderen;
- persoonlijke klikpositie zichtbaar en onderdeel van de gegenereerde route;
- replay van misklik en herstelbeweging;
- specifieke foutafhandeling en lokaal logbestand;
- snelle Windows-launcher;
- automatische tests op Windows en Linux;
- alle versie- en projectmetadata synchroniseren.

## Eerstvolgende mogelijke verbetering

### Raw Input Recorder — Enhancement

Alleen bouwen wanneer er een concrete behoefte is om gamebewegingen te analyseren. Dit moet een aparte relatieve `dx/dy`-recorder zijn en mag nooit stilzwijgend met Aim Lab-profieldata worden gemengd.

Verwachte waarde: betrouwbare 360°-bewegingen, flicks en cameradraai registreren.

Complexiteit: middelgroot; Windows Raw Input, aparte datastructuur en eigen validatie nodig.

## Niet gepland

- automatische externe muisbesturing;
- gamebots of click automation;
- cloudplatform;
- algemene desktoprecorder;
- nieuwe UI-functies voordat de kernflow lokaal volledig is bevestigd.
