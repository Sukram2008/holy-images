# HOLY Images

Zentrale Bildablage für das HOLY Inventar- und Bewertungsmodul. Sorten- und Shakerbilder werden getrennt gehalten und über jsDelivr ausgeliefert.

## Ordnerstruktur

```text
holy-images/
├── sorten/
│   ├── energy/
│   ├── iced-tea/
│   ├── hydration/
│   ├── milkshake/
│   └── syrup/
└── shaker/
    ├── energy/                 (44 Bilder)
    ├── iced-tea/               (23 Bilder)
    ├── hydration/              (20 Bilder)
    ├── milkshake/               (10 Bilder)
    ├── spezial/                 (66 Bilder)
    ├── xl/                      (11 Bilder)
    ├── giga-gallon/             (7 Bilder)
    ├── glasflasche/             (26 Bilder)
    ├── thermo/                  (95 Bilder)
    ├── creator-de/              (59 Bilder)
    ├── creator-de-xl/           (8 Bilder)
    ├── creator-de-thermo/       (9 Bilder)
    ├── creator-fr/              (27 Bilder)
    ├── creator-fr-thermo/       (18 Bilder)
    ├── creator-fr-glasflasche/  (2 Bilder)
    ├── creator-uk/              (3 Bilder)
    └── sport-flasche/            (2 Bilder)
```

Zusätzlich werden unter `thumbs/` zu jedem Shaker-Original quadratische Discord-Vorschaubilder erzeugt. Sie sind 512×512 px, transparent und proportional eingepasst (contain, kein Crop). Die Originale unter `shaker/` bleiben unverändert und eignen sich weiterhin für große Ansichten.

Der zugehörige Shaker-Katalog enthält aktuell **433 Einträge in 18 Kategorien**. Die Zahlen sind Kategorieeinträge; gleiche Produkte in unterschiedlichen Variantenkategorien werden separat gezählt.

## Dateinamen

Sortenbilder: `<Kategorie>_#<Nummer>_<Produktname>.<Format>`  
Shakerbilder: `<Kategorie>_#<Nummer>_<Produktname>.<Format>`

Beispiele:
- `sorten/energy/Energy_#1_Raspberry-Raptor.webp`
- `shaker/energy/Energy_#01_Raptor.webp`
- `shaker/iced-tea/Iced-Tea_#01_Peach.webp`

## CDN-URL

```text
https://cdn.jsdelivr.net/gh/Sukram2008/holy-images@main/PFAD/DATEI
```

Die Datei muss unter exakt diesem Pfad im öffentlichen Repository liegen. Dateipfade sind case-sensitive.

## Automatische Importe

- `Import OchDenis Tub images`: liest die Sortenübersicht und übernimmt je Sorte das erste Produktbild.
- `Import OchDenis shaker images`: übernimmt Bilder aus den regulären Kategorien Energy, Iced Tea, Hydration und Milkshake. Alternative Kategorien wie `Energy (Alt Bunt)`, `Energy (Alt Schwarz)` und `Iced Tea (Alt Schwarz)` bleiben ausgeschlossen.
- `Import OchDenis Spezial shaker images`: übernimmt alle 66 Einträge der Kategorie Spezial.
- `Import OchDenis XL shaker images`: übernimmt alle 11 Einträge der Kategorie XL.
- `Import OchDenis Giga Gallon and Glasflasche shaker images`: übernimmt 7 Giga-Gallon-Modelle und 26 Glasflaschen aus den gleichnamigen Kategorien.
- `Import OchDenis Thermo shaker images`: übernimmt alle 95 Produkte der exakten Hauptkategorie `Thermo` (nicht die getrennten Creator-Kategorien).
- `Import OchDenis Creator-DE shaker images`: übernimmt die drei getrennten Kategorien `Creator - DE` (59), `Creator - DE - XL` (8) und `Creator - DE - Thermo` (9).
- `Import OchDenis international shaker categories`: übernimmt `Creator - FR` (27), `Creator - FR - Thermo` (18), `Creator - FR - Glasflasche` (2), `Creator - UK` (3) und `Sport-Flasche` (2).


Alle Importe prüfen Dateityp und Bilddaten und committen die Ergebnisse gesammelt. Schlägt eine Bildprüfung fehl, bricht der Import ab, statt einen unvollständigen Katalog als erfolgreich zu melden.

## Hinweise

- Bevorzugte Formate: WebP; PNG und JPEG sind ebenfalls erlaubt.
- Dateiendung muss dem tatsächlichen Bildformat entsprechen.
- Nur eindeutig zugeordnete Produktbilder verwenden.
- jsDelivr cached Dateien. Bei Bildwechsel unter demselben Pfad kann es eine Weile dauern, bis die neue Version überall sichtbar ist.
- Keine privaten oder vertraulichen Dateien hochladen.


## Compact CDN aliases

Original product image files remain in their category folders. The `s/` directory contains short GitHub-blob aliases for efficient jsDelivr URLs:
- `s/e###.webp`: standard Energy
- `s/i###.webp`: standard Iced Tea
- `s/h###.webp`: standard Hydration
- `s/m###.webp`: standard Milkshake
- `s/p##.webp`: Spezial
- `s/x##.webp`: XL
- `s/gg##.webp`: Giga Gallon
- `s/gf##.webp`: Glasflasche
- `s/th###.webp`: Thermo
- `s/cd###.webp`: Creator - DE
- `s/cx##.webp`: Creator - DE - XL
- `s/ct##.webp`: Creator - DE - Thermo

The aliases point to the same Git blobs; no image is recompressed or changed.

## Discord thumbnails

- `thumbs/` mirrors the complete `shaker/` folder structure.
- Every thumbnail is 512×512 WebP with transparent padding and the complete image fitted inside a 464×464 px area.
- Thumbnails use `contain` scaling and never crop the shaker cap, body, or base.
- Original images are not modified.
- `.github/scripts/build_shaker_thumbnails.py` rebuilds all thumbnails; the standard shaker import also creates a thumbnail alongside each newly imported original.
