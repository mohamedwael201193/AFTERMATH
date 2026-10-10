/**
 * AFTERMATH artwork keyer v2.
 * Corner-sampled background color + border flood fill + feathered unmixing
 * + small-island cleanup. Handles any flat isolation background color and
 * protects same-colored interior details (e.g. coral cheeks) behind the
 * sticker border.
 *
 * Run: bun scripts/process-artwork.ts
 */
import sharp from "sharp";
import { readdir } from "node:fs/promises";
import path from "node:path";

const ART_DIR = "/home/z/my-project/public/artwork";
const T_CORE = 70; // flood membership distance
const T_GLOBAL = 58; // global color-key distance (removes enclosed pockets)
const T_EDGE = 175; // feather band outer distance
const ISLAND_MAX = 4000; // px area below which stray opaque islands are removed

function dist(r: number, g: number, b: number, br: number, bg: number, bb: number) {
  const dr = r - br, dg = g - bg, db = b - bb;
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

async function processFile(file: string): Promise<void> {
  const inPath = path.join(ART_DIR, file);
  const outPath = path.join(ART_DIR, file.replace(/\.png$/, ".keyed.png"));

  const { data, info } = await sharp(inPath).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const W = info.width, H = info.height, CH = info.channels;
  const out = Buffer.from(data);

  // ── 1. sample background color: median of border strip pixels ──
  const border: number[][] = [];
  const step = 4;
  for (let x = 0; x < W; x += step) {
    for (const y of [0, 1, H - 2, H - 1]) {
      const i = (y * W + x) * CH;
      border.push([data[i], data[i + 1], data[i + 2]]);
    }
  }
  for (let y = 0; y < H; y += step) {
    for (const x of [0, 1, W - 2, W - 1]) {
      const i = (y * W + x) * CH;
      border.push([data[i], data[i + 1], data[i + 2]]);
    }
  }
  const med = (idx: number) => {
    const vals = border.map((b) => b[idx]).sort((a, b) => a - b);
    return vals[Math.floor(vals.length / 2)];
  };
  const BK = [med(0), med(1), med(2)];
  console.log(`  bg sample: rgb(${BK.join(",")})`);

  // ── 2. flood fill background region from the borders ──
  const member = new Uint8Array(W * H);
  const queue = new Int32Array(W * H);
  let qh = 0, qt = 0;
  const push = (p: number) => {
    if (!member[p]) {
      const i = p * CH;
      const d = dist(data[i], data[i + 1], data[i + 2], BK[0], BK[1], BK[2]);
      if (d < T_CORE) {
        member[p] = 1;
        queue[qt++] = p;
      }
    }
  };
  for (let x = 0; x < W; x++) {
    push(x);
    push((H - 1) * W + x);
  }
  for (let y = 0; y < H; y++) {
    push(y * W);
    push(y * W + W - 1);
  }
  while (qh < qt) {
    const p = queue[qh++];
    const px = p % W, py = (p - px) / W;
    if (px > 0) push(p - 1);
    if (px < W - 1) push(p + 1);
    if (py > 0) push(p - W);
    if (py < H - 1) push(p + W);
  }

  // ── 3. zero alpha on members; feather neighbors ──
  for (let p = 0; p < W * H; p++) {
    if (member[p]) {
      out[p * CH + 3] = 0;
      continue;
    }
    // check 8-neighborhood for a member (edge feather candidates)
    const px = p % W, py = (p - px) / W;
    let touches = false;
    for (let dy = -1; dy <= 1 && !touches; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const nx = px + dx, ny = py + dy;
        if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
        if (member[ny * W + nx]) { touches = true; break; }
      }
    }
    if (!touches) continue;
    const i = p * CH;
    const d = dist(data[i], data[i + 1], data[i + 2], BK[0], BK[1], BK[2]);
    if (d >= T_EDGE) continue;
    let alpha = (d - T_CORE) / (T_EDGE - T_CORE);
    if (alpha < 0.05) {
      out[i + 3] = 0;
      continue;
    }
    alpha = Math.min(1, alpha);
    out[i + 3] = Math.round(255 * alpha);
    // unmix background contribution from the kept color
    for (let c = 0; c < 3; c++) {
      const unmixed = BK[c] + (data[i + c] - BK[c]) / alpha;
      out[i + c] = Math.max(0, Math.min(255, Math.round(unmixed)));
    }
  }

  // ── 3b. global color key — removes enclosed background pockets ──
  const keyed = new Uint8Array(W * H);
  for (let p = 0; p < W * H; p++) {
    if (member[p]) continue;
    const i = p * CH;
    const d = dist(data[i], data[i + 1], data[i + 2], BK[0], BK[1], BK[2]);
    if (d < T_GLOBAL) {
      out[i + 3] = 0;
      keyed[p] = 1;
    }
  }

  // ── 4. feather every pixel that borders transparency (flood or global) ──
  const transparent = (p: number) => member[p] === 1 || keyed[p] === 1;
  for (let p = 0; p < W * H; p++) {
    if (transparent(p) || out[p * CH + 3] === 0) continue;
    const px = p % W, py = (p - px) / W;
    let touches = false;
    for (let dy = -1; dy <= 1 && !touches; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const nx = px + dx, ny = py + dy;
        if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
        if (transparent(ny * W + nx)) { touches = true; break; }
      }
    }
    if (!touches) continue;
    const i = p * CH;
    const d = dist(data[i], data[i + 1], data[i + 2], BK[0], BK[1], BK[2]);
    if (d >= T_EDGE) continue;
    let alpha = (d - T_GLOBAL) / (T_EDGE - T_GLOBAL);
    if (alpha < 0.05) {
      out[i + 3] = 0;
      continue;
    }
    alpha = Math.min(1, alpha);
    out[i + 3] = Math.round(255 * alpha);
    // unmix background contribution from the kept color
    for (let c = 0; c < 3; c++) {
      const unmixed = BK[c] + (data[i + c] - BK[c]) / alpha;
      out[i + c] = Math.max(0, Math.min(255, Math.round(unmixed)));
    }
  }

  // ── 5. remove tiny opaque islands (stray specks, pattern dots) ──
  {
    const seen = new Uint8Array(W * H);
    const stack = new Int32Array(W * H);
    const comp = new Int32Array(1024);
    for (let p0 = 0; p0 < W * H; p0++) {
      if (seen[p0] || out[p0 * CH + 3] < 25) continue;
      // BFS this component
      let sp = 0, size = 0;
      stack[sp++] = p0;
      seen[p0] = 1;
      const members: number[] = [];
      while (sp > 0) {
        const p = stack[--sp];
        members.push(p);
        size++;
        const px = p % W, py = (p - px) / W;
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            const nx = px + dx, ny = py + dy;
            if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
            const np = ny * W + nx;
            if (!seen[np] && out[np * CH + 3] >= 25) {
              seen[np] = 1;
              stack[sp++] = np;
            }
          }
        }
      }
      if (size < ISLAND_MAX) {
        for (const p of members) out[p * CH + 3] = 0;
      }
      void comp;
    }
  }

  await sharp(out, { raw: { width: W, height: H, channels: 4 as const } })
    .png({ compressionLevel: 9 })
    .toFile(outPath);
  console.log(`✓ ${file} -> ${path.basename(outPath)}`);
}

async function main() {
  const files = (await readdir(ART_DIR)).filter(
    (f) => f.endsWith(".png") && !f.includes(".keyed.")
  );
  console.log(`Keying ${files.length} artwork files…`);
  for (const f of files) {
    try {
      await processFile(f);
    } catch (err) {
      console.error(`✗ ${f}:`, err);
    }
  }
}

main();
