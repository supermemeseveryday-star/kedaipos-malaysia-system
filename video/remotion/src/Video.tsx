import React from 'react';
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, Series, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import timeline from './timeline.json';
import { Anywhere, Checkout, Owner, Overview, Payment, Receipt } from './scenes';
import { Line, Subtitles } from './ui';

export const FPS = 30;
type Scene = { id: string; kind?: string; seconds: number; lines: Line[] };
const scenes = timeline.scenes as Scene[];
export const totalFrames = scenes.reduce((n, s) => n + Math.round(s.seconds * FPS), 0);

const visuals: Record<string, React.FC<{ lines: Line[]; seconds: number }>> = {
  overview: Overview, checkout: Checkout, payment: Payment, receipt: Receipt, owner: Owner, anywhere: Anywhere,
};

/** Fades a scene in and out against the page background so cuts feel soft. */
const Fade: React.FC<{ frames: number; edges: boolean; children: React.ReactNode }> = ({ frames, edges, children }) => {
  const frame = useCurrentFrame();
  const f = 9;
  const opacity = edges ? interpolate(frame, [0, f, frames - f, frames], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 1;
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

const SceneView: React.FC<{ scene: Scene; frames: number }> = ({ scene, frames }) => {
  const { fps } = useVideoConfig();
  const Visual = visuals[scene.id];
  return (
    <AbsoluteFill style={{ background: '#f4f6f4' }}>
      <Fade frames={frames} edges={!scene.kind}>
        {scene.kind === 'hyperframes'
          ? <OffthreadVideo src={staticFile(`hf/${scene.id}.mp4`)} muted />
          : <Visual lines={scene.lines} seconds={scene.seconds} />}
      </Fade>
      {scene.lines.map(line => (
        <Sequence key={line.file} from={Math.round(line.start * fps)} layout="none">
          <Audio src={staticFile(line.file)} />
        </Sequence>
      ))}
      <Subtitles lines={scene.lines} />
    </AbsoluteFill>
  );
};

export const KedaiPosIntro: React.FC = () => (
  <Series>
    {scenes.map(scene => {
      const frames = Math.round(scene.seconds * FPS);
      return (
        <Series.Sequence key={scene.id} durationInFrames={frames} name={scene.id}>
          <SceneView scene={scene} frames={frames} />
        </Series.Sequence>
      );
    })}
  </Series>
);
