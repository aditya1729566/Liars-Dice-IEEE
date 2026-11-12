import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '../..');
const runtime = resolve(root, 'web/runtime');
mkdirSync(resolve(runtime, 'policies'), { recursive: true });
mkdirSync(resolve(runtime, 'docs'), { recursive: true });
for (const name of ['fixed5_cfr.json', 'fixed5_cfr_v2.json', 'mccfr_external_v1.bin', 'index.json']) {
  cpSync(resolve(root, 'policies', name), resolve(runtime, 'policies', name));
}
cpSync(resolve(root, 'docs/research_runs.json'), resolve(runtime, 'docs/research_runs.json'));
const compiler = process.platform === 'darwin' ? 'clang++' : 'g++';
if (!existsSync(resolve(root, 'engine/src/main.cpp'))) throw Error('Engine source is missing');
execFileSync(compiler, ['-std=c++20', '-O2', resolve(root, 'engine/src/main.cpp'), '-o', resolve(runtime, 'bluff_engine')], { stdio: 'inherit' });
