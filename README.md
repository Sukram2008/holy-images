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
    ├── energy/
    ├── iced-tea/
    ├── hydration/
    ├── milkshake/
    └── spezial/  (65 Bilder)
```

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
- `Import OchDenis Spezial shaker images`: übernimmt alle 65 Einträge der Kategorie Spezial.

Beide Importe prüfen Dateityp und Bilddaten und committen die Ergebnisse gesammelt. Schlägt eine Bildprüfung fehl, bricht der Import ab, statt einen unvollständigen Katalog als erfolgreich zu melden.

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

The aliases point to the same Git blobs; no image is recompressed or changed.
