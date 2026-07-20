#!/usr/bin/env bash
# Regenerate the PWA icons (frontend/public/icons/) with ImageMagick.
# Green rounded tile with a white "M" — masareef's quick-add brand mark.
set -euo pipefail
cd "$(dirname "$0")/../frontend/public/icons"

GREEN="#0e9f6e"

# Rounded-square app icon (transparent corners).
rounded() { # size radius out
  magick -size "$1x$1" xc:none \
    -fill "$GREEN" -draw "roundrectangle 0,0 $(($1 - 1)),$(($1 - 1)) $2,$2" \
    -fill white -font DejaVu-Sans -weight Bold -pointsize "$(($1 * 55 / 100))" \
    -gravity center -annotate +0+"$(($1 * 2 / 100))" "M" \
    "$3"
}

rounded 192 38 icon-192.png
rounded 512 100 icon-512.png
rounded 180 36 apple-touch-icon.png

# Maskable: full-bleed background, glyph inside the 80% safe zone.
magick -size 512x512 "xc:$GREEN" \
  -fill white -font DejaVu-Sans -weight Bold -pointsize 240 \
  -gravity center -annotate +0+10 "M" \
  icon-maskable-512.png

echo "icons regenerated:"
ls -la
