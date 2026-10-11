// Generates the Chinese voiceover, one WAV per subtitle line, with the HyperFrames
// local TTS (Kokoro-82M), then writes remotion/src/timeline.json with each line's
// exact duration and start time, so subtitles and scenes follow the voice.
//
// Usage (from video/): node make-voice.mjs
// Needs: hyperframes (npm, in hyperframes/), Python with kokoro-onnx + soundfile, ffprobe.
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const script = JSON.parse(readFileSync(join(here, 'script.json'), 'utf8'));
const hfBin = join(here, 'hyperframes', 'node_modules', '.bin', 'hyperframes');
const voiceDir = join(here, 'remotion', 'public', 'voice');
mkdirSync(voiceDir, { recursive: true });

const force = process.argv.includes('--force');
const duration = file => Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]).toString().trim());

const timeline = { voice: script.voice, scenes: [] };
for (const scene of script.scenes) {
  const lines = [];
  scene.lines.forEach((line, i) => {
    const name = `${scene.id}-${i + 1}.wav`;
    const out = join(voiceDir, name);
    if (force || !existsSync(out)) {
      execFileSync(hfBin, ['tts', line.zh, '-v', script.voice, '-s', String(script.speed), '-o', out], { stdio: ['ignore', 'ignore', 'inherit'] });
    }
    const seconds = duration(out);
    lines.push({ ...line, file: `voice/${name}`, seconds: Math.round(seconds * 1000) / 1000 });
    console.log(`${name.padEnd(16)} ${seconds.toFixed(2)}s  ${line.zh}`);
  });
  // Scene-local timing: a lead-in, a short pause between sentences, then a tail.
  const branded = scene.kind === 'hyperframes';
  let t = branded ? 0.8 : 0.5;
  for (const line of lines) {
    line.start = Math.round(t * 1000) / 1000;
    t += line.seconds + 0.35;
  }
  const seconds = Math.round((t - 0.35 + (branded ? 1.6 : 0.7)) * 1000) / 1000;
  const { lines: _, ...rest } = scene;
  timeline.scenes.push({ ...rest, seconds, lines });
}
writeFileSync(join(here, 'remotion', 'src', 'timeline.json'), JSON.stringify(timeline, null, 2) + '\n');
const total = timeline.scenes.flatMap(s => s.lines).reduce((t, l) => t + l.seconds, 0);
const runtime = timeline.scenes.reduce((t, s) => t + s.seconds, 0);
console.log(`\n${timeline.scenes.flatMap(s => s.lines).length} lines, ${total.toFixed(1)}s of speech, ${runtime.toFixed(1)}s of scenes`);
