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
    └── milkshake/
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

Beide Importe prüfen Dateityp und Bilddaten und committen die Ergebnisse gesammelt. Schlägt eine Bildprüfung fehl, bricht der Import ab, statt einen unvollständigen Katalog als erfolgreich zu melden.

## Hinweise

- Bevorzugte Formate: WebP; PNG und JPEG sind ebenfalls erlaubt.
- Dateiendung muss dem tatsächlichen Bildformat entsprechen.
- Nur eindeutig zugeordnete Produktbilder verwenden.
- jsDelivr cached Dateien. Bei Bildwechsel unter demselben Pfad kann es eine Weile dauern, bis die neue Version überall sichtbar ist.
- Keine privaten oder vertraulichen Dateien hochladen.
