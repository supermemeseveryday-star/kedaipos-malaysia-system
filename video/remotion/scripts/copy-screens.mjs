// Copies the README screenshots into public/screens so Remotion can load them.
import { cpSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const from = join(here, '..', '..', '..', 'docs', 'screenshots');
const to = join(here, '..', 'public', 'screens');
mkdirSync(to, { recursive: true });
for (const f of readdirSync(from).filter(f => f.endsWith('.png'))) cpSync(join(from, f), join(to, f));
console.log(`copied screenshots to ${to}`);
