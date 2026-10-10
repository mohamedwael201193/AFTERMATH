#!/bin/bash
# AFTERMATH original artwork generation — consistent sticker illustration family
# All assets isolated on flat magenta for chroma-key transparency extraction.
set -u
OUT="/home/z/my-project/public/artwork"
mkdir -p "$OUT"

STYLE="Original retro cartoon sticker illustration, thick bold black ink outlines, flat warm cream ivory fill colors, deep forest green and muted sage green accents, subtle stipple shading texture, die-cut sticker style with thick cream-white border around the artwork, single centered subject, isolated on a solid flat bright magenta background, absolutely no text, no letters, no numbers, no watermark, clean professional vector-like flat finish, high quality"

gen() {
  local name="$1"; local size="$2"; local prompt="$3"
  if [ -f "$OUT/$name" ]; then echo "skip $name (exists)"; return 0; fi
  echo "=== generating $name ($size) ==="
  z-ai image -p "$prompt, $STYLE" -o "$OUT/$name" -s "$size" && echo "done $name" || echo "FAILED $name"
}

gen "sentinel-hero.png" "864x1152" "A friendly guardian character made of an anthropomorphic paper receipt document, standing confidently with legs and white sneaker shoes, one arm raised high holding up a glowing green verified receipt paper with a bold checkmark stamp on it, wearing a small deep forest green visor cap, round dot eyes with a confident calm expression, small shield emblem badge on its chest, heroic dynamic pose" &

gen "risk-guardian.png" "1024x1024" "A sturdy round shield character with a stern but kind face and stubby arms, firmly stopping a bold red downward zigzag arrow with its flat hand, a small green toll gate barrier arm standing beside the shield, determined protective stance" &

gen "evidence-flow.png" "1344x768" "Three cheerful paper document characters with tiny legs walking in a row, the first holds a magnifying glass, the second carries a stamped checkmark paper, the third points forward, small gold coins and tiny green chart arrows orbiting above them, wide horizontal landscape composition" &

gen "receipt-seal.png" "1024x1024" "A proud paper receipt roll character standing upright with a glossy deep green wax seal stamp pressed on its chest, a green ribbon trailing down, a small round checkmark badge and a tiny vintage key floating beside it, happy proud expression" &

gen "empty-search.png" "1024x1024" "A small curious paper document character holding a big magnifying glass up to its face searching for something, floating question marks and empty dashed outline boxes around it, head tilted with a puzzled expression" &

gen "after-hours.png" "1344x768" "A shocked retro twin-bell alarm clock character with wide eyes looking at a standing price chart board showing a bold gap arrow, a crescent moon with tiny stars above, a simple deep green night city skyline silhouette below, wide horizontal landscape composition" &

wait
echo "ALL ARTWORK DONE"
ls -la "$OUT"
