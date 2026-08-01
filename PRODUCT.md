# Productcontract — AI Mouse Lab

## Primaire taak

AI Mouse Lab neemt persoonlijke targetgerichte muisbewegingen op en vergelijkt die met bewegingen die uit hetzelfde persoonlijke profiel zijn gegenereerd.

De kernflow is:

1. Aim Lab-sessie opnemen.
2. Persoonlijk profiel bouwen uit geldige normale sessies.
3. De nieuwste sessie als vaste A/B-targetplaylist gebruiken.
4. Menselijke A en gegenereerde B volledig en controleerbaar afspelen.

## Productcategorie

**Core**

Alles in de actieve app moet direct bijdragen aan opnemen, profileren, genereren of vergelijken.

## Betrouwbaarheidsregels

- Aim Lab is de enige trainingsbron.
- Detectietests trainen het profiel niet.
- Ruwe routepunten blijven bewaard zodat metrics later opnieuw berekend kunnen worden.
- A en B gebruiken exact dezelfde starts, targets en targetgroottes.
- De generator eindigt op de persoonlijk gesamplede klikpositie, niet automatisch op het middelpunt.
- Ongeldige of onvolledige data wordt afgewezen met een zichtbare reden.
- Lokale gebruikersdata wordt niet automatisch verwijderd.

## Definitie van succes

De versie is geslaagd wanneer:

- de test-suite volledig groen is;
- de Windows-launcher zonder herinstallatie bij iedere start opent;
- Aim Lab → Build Profile → A/B → volledige replay zonder fout werkt;
- replay de echte klikposities en misklikken zichtbaar toont;
- versienummer, changelog en Turbo Repo Hub-metadata overeenkomen;
- de actieve code geen patchketen, legacy-wrapper of Free Record-flow bevat.

## Bewust niet gebouwd

- raw-inputopname voor games;
- externe muisbesturing;
- image detection of automatische clicks;
- cloudopslag;
- database;
- automatische classifier.
