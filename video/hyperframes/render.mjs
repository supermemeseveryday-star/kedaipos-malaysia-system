// Renders the HyperFrames intro/outro to MP4 for Remotion, timed to the voiceover.
// Usage (from video/hyperframes/): node render.mjs [--draft]
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const timeline = JSON.parse(readFileSync(join(here, '..', 'remotion', 'src', 'timeline.json'), 'utf8'));
const outDir = join(here, '..', 'remotion', 'public', 'hf');
mkdirSync(outDir, { recursive: true });
const quality = process.argv.includes('--draft') ? 'draft' : 'delivery';

for (const id of ['intro', 'outro']) {
  const scene = timeline.scenes.find(s => s.id === id);
  const vars = { dur: scene.seconds + 0.5 };
  scene.lines.forEach((line, i) => { if (i) vars[`t${i + 1}`] = line.start; });
  const varsFile = join(here, `.vars-${id}.json`);
  writeFileSync(varsFile, JSON.stringify(vars));
  console.log(`${id}: ${JSON.stringify(vars)}`);
  execFileSync(join(here, 'node_modules', '.bin', 'hyperframes'),
    ['render', here, '-c', `compositions/${id}.html`, '--variables-file', varsFile, '-q', quality, '-f', '30', '-o', join(outDir, `${id}.mp4`), '--quiet'],
    { stdio: 'inherit', env: { ...process.env, HYPERFRAMES_NO_TELEMETRY: '1' } });
}
