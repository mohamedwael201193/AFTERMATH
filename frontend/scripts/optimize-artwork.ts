/**
 * AFTERMATH artwork optimization pass.
 * 1. Trim to the alpha bounding box (predictable layout margins).
 * 2. Resize to sensible web dimensions.
 * 3. Re-encode as palette PNG (dithered) for small files.
 * Run: bun scripts/optimize-artwork.ts
 */
import sharp from "sharp";
import { readdir } from "node:fs/promises";
import path from "node:path";

const ART_DIR = "/home/z/my-project/public/artwork";

const TARGET_WIDTHS: Record<string, number> = {
  "sentinel-hero.keyed.png": 780,
  "risk-guardian.keyed.png": 640,
  "receipt-seal.keyed.png": 520,
  "evidence-flow.keyed.png": 900,
  "empty-search.keyed.png": 560,
  "after-hours.keyed.png": 900,
};

async function optimize(file: string): Promise<void> {
  const p = path.join(ART_DIR, file);
  const targetW = TARGET_WIDTHS[file] ?? 720;

  // 1. compute alpha bounding box
  const { data, info } = await sharp(p).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const ch = info.channels;
  let minX = info.width, minY = info.height, maxX = -1, maxY = -1;
  for (let y = 0; y < info.height; y++) {
    for (let x = 0; x < info.width; x++) {
      const a = data[(y * info.width + x) * ch + 3];
      if (a > 8) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (maxX < 0) {
    console.error(`✗ ${file}: fully transparent?`);
    return;
  }
  const pad = 6; // keep a hair of margin
  const left = Math.max(0, minX - pad);
  const top = Math.max(0, minY - pad);
  const width = Math.min(info.width - left, maxX - minX + pad * 2 + 1);
  const height = Math.min(info.height - top, maxY - minY + pad * 2 + 1);

  // 2 + 3. crop, resize, palette-encode
  const outW = Math.min(targetW, width);
  const buf = await sharp(p)
    .extract({ left, top, width, height })
    .resize({ width: outW })
    .png({ palette: true, quality: 90, compressionLevel: 9, dither: 1.0 })
    .toFile(p + ".tmp");

  const { default: fs } = await import("node:fs");
  fs.renameSync(p + ".tmp", p);
  const meta = await sharp(p).metadata();
  console.log(
    `✓ ${file}: crop ${width}x${height} → ${meta.width}x${meta.height}, ${(buf.size / 1024).toFixed(0)} KB`
  );
}

async function main() {
  const files = (await readdir(ART_DIR)).filter((f) => f.endsWith(".keyed.png"));
  for (const f of files) {
    try {
      await optimize(f);
    } catch (err) {
      console.error(`✗ ${f}:`, err);
    }
  }
}

main();
