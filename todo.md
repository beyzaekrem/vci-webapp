# To Do GUI-Client

## Features

- Dropdown für Auswahl, welche Clients in Grid gezeigt werden
- Operationen für mehrere Kameras:
  - Download von den Bildern aller angezeigter Kameras
  - Implementierung Button "Set Value for multiple Cameras"
  - Starten von Streams aller angezeigten Kameras
  - Beim Anzeigen von vielen Kameras Kann es gut sein dass die Auflösung niedriger gewählt werden muss. Lieber a oder b?
    - a Automatisches Setzen von niedriger Auflösung, wenn sehr viele Kameras angezeigt werden
      - => was, wenn kameras in verschiedenen Tabs offen sind? Tritt dieser Fall ein, will der Nutzer das
    - b Button in dreipunktmenü zum setzne von Auflösung von einer/ mehreren Kameras

# Umgesetzt

- Integer-Zoom für Quadratische Bilder => passt so?
- Länge des Papers maximal/ minimal?
- Manifest, aber nicht mehr einbauen
- Weiterarbeiten?
- CLI: Operationen für alle Server mit Keyword "all"
- CLI: abkürzungen für bestimmte urls in config festlegbar
- Favoriten Parameter

# To Do

- Versuchen, glitches bei offset zu beheben
- Herausfinden, warum selecten von cameras so buggy ist
- CLI url angeben geht nicht
- jar bauen

# Zukünftige Features

... die aus Zeitgründen noch nicht umgesetzt wurden:

- Shortcuts im GUI-Client
  - plus minus exposure
  - mausrad zoom etc
- Während Zoom Lens aktiv ist, sollen Buttons für Offset von serverseitigem Zoom benutzt werden können
- Zoom Lens ist dauerhaft aktiviert
- Bei Verwendung der Zoom Lens wird das Pixel in der Mitte der Lupe markiert und dessen RGB-Wert angezeigt
