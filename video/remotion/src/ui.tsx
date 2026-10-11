import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

export const C = {
  green: '#15583d', green2: '#1e704d', mint: '#e8f3ec', ink: '#17231e', muted: '#76827b',
  paper: '#f4f6f4', red: '#b9443d', gold: '#9b6a12', line: '#e7ebe8',
};
export const ZH = '"WenQuanYi Zen Hei", "Noto Sans SC", "PingFang SC", sans-serif';
export const EN = 'Inter, "Helvetica Neue", Arial, sans-serif';

/** Scene-local time in seconds. */
export const useTime = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
};

const ease = Easing.bezier(0.33, 1, 0.68, 1);
/** 0→1 over [start, start+duration], eased. */
export const ramp = (t: number, start: number, duration = 0.6) =>
  interpolate(t, [start, start + duration], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });

export const usePop = (start: number) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  return spring({ frame: frame - start * fps, fps, config: { damping: 14, stiffness: 140 } });
};

export const Backdrop: React.FC<{ tint?: string }> = ({ tint = C.mint }) => {
  const t = useTime();
  return (
    <AbsoluteFill style={{ background: C.paper, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', width: 1100, height: 1100, borderRadius: '50%', left: -300 + t * 6, top: -520, background: `radial-gradient(circle, ${tint} 0%, #f4f6f400 65%)` }} />
      <div style={{ position: 'absolute', width: 900, height: 900, borderRadius: '50%', right: -260 - t * 5, bottom: -480, background: 'radial-gradient(circle, #dcebe2 0%, #f4f6f400 65%)' }} />
    </AbsoluteFill>
  );
};

/** A camera keyframe: centre the point (x, y) — fractions of the screenshot — at zoom `scale`. */
export type Shot = { at: number; x: number; y: number; scale: number };

const cameraAt = (shots: Shot[], t: number) => {
  if (t <= shots[0].at) return shots[0];
  for (let i = 1; i < shots.length; i++) {
    const a = shots[i - 1], b = shots[i];
    if (t <= b.at) {
      const k = interpolate(t, [a.at, b.at], [0, 1], { easing: Easing.inOut(Easing.cubic) });
      return { at: t, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, scale: a.scale + (b.scale - a.scale) * k };
    }
  }
  return shots[shots.length - 1];
};

/** Screenshot inside a browser window, with a moving camera. Children are positioned in screenshot fractions and move with it. */
export const BrowserShot: React.FC<{
  src: string; shots: Shot[]; width?: number; left?: number; top?: number; opacity?: number; children?: React.ReactNode;
}> = ({ src, shots, width = 1240, left, top = 40, opacity = 1, children }) => {
  const t = useTime();
  const W = width, H = Math.round(width / 1.6), bar = 42;
  const cam = cameraAt(shots, t);
  const s = cam.scale;
  const x = Math.min(0, Math.max(W - W * s, W / 2 - cam.x * W * s));
  const y = Math.min(0, Math.max(H - H * s, H / 2 - cam.y * H * s));
  return (
    <div style={{ position: 'absolute', left: left ?? (1920 - W) / 2, top, width: W, height: H + bar, borderRadius: 18, overflow: 'hidden', background: '#fff', boxShadow: '0 40px 90px #142b1b2e, 0 0 0 1px #142b1b14', opacity }}>
      <div style={{ height: bar, background: '#eef1ef', display: 'flex', alignItems: 'center', gap: 9, padding: '0 18px' }}>
        {['#e26a5a', '#e7b53e', '#5bb36a'].map(c => <div key={c} style={{ width: 13, height: 13, borderRadius: '50%', background: c }} />)}
        <div style={{ marginLeft: 18, height: 26, flex: 1, maxWidth: 420, borderRadius: 8, background: '#fff', font: `500 15px ${EN}`, color: C.muted, display: 'flex', alignItems: 'center', paddingLeft: 14 }}>localhost:8765</div>
      </div>
      <div style={{ position: 'relative', width: W, height: H, overflow: 'hidden' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, width: W, height: H, transformOrigin: '0 0', transform: `translate(${x}px, ${y}px) scale(${s})` }}>
          <Img src={staticFile(`screens/${src}`)} style={{ width: W, height: H, display: 'block' }} />
          {children}
        </div>
      </div>
    </div>
  );
};

/** Rounded highlight box in screenshot fractions; draws in at `at`. */
export const Box: React.FC<{ x0: number; y0: number; x1: number; y1: number; at: number; until?: number; color?: string }> = ({ x0, y0, x1, y1, at, until = 1e9, color = C.green }) => {
  const t = useTime();
  const k = ramp(t, at, 0.45) * (1 - ramp(t, until, 0.3));
  return (
    <div style={{ position: 'absolute', left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%`, border: `4px solid ${color}`, borderRadius: 14, boxShadow: `0 0 0 ${8 * k}px ${color}26`, opacity: k, transform: `scale(${1.06 - 0.06 * k})` }} />
  );
};

/** A finger-tap ripple in screenshot fractions. */
export const Tap: React.FC<{ x: number; y: number; at: number }> = ({ x, y, at }) => {
  const t = useTime();
  if (t < at - 0.3 || t > at + 0.9) return null;
  const press = ramp(t, at - 0.3, 0.3);
  const ring = ramp(t, at, 0.7);
  return (
    <div style={{ position: 'absolute', left: `${x * 100}%`, top: `${y * 100}%` }}>
      <div style={{ position: 'absolute', width: 70, height: 70, left: -35, top: -35, borderRadius: '50%', border: `4px solid ${C.green}`, opacity: 1 - ring, transform: `scale(${0.5 + ring * 1.4})` }} />
      <div style={{ position: 'absolute', width: 36, height: 36, left: -18, top: -18, borderRadius: '50%', background: `${C.green}aa`, opacity: press * (1 - ring), transform: `scale(${1.3 - 0.3 * press})` }} />
    </div>
  );
};

export const Phone: React.FC<{ src: string; left: number; top: number; height?: number; style?: React.CSSProperties; scroll?: number }> = ({ src, left, top, height = 760, style, scroll = 0 }) => {
  const width = Math.round(height * 780 / 1688);
  return (
    <div style={{ position: 'absolute', left, top, width: width + 28, height: height + 28, borderRadius: 64, background: '#121a16', padding: 14, boxShadow: '0 40px 90px #142b1b40', ...style }}>
      <div style={{ width, height, borderRadius: 52, overflow: 'hidden', position: 'relative', background: '#fff' }}>
        <Img src={staticFile(`screens/${src}`)} style={{ width, display: 'block', transform: `translateY(${-scroll}px)` }} />
        <div style={{ position: 'absolute', top: 12, left: '50%', width: 110, height: 30, marginLeft: -55, borderRadius: 20, background: '#121a16' }} />
      </div>
    </div>
  );
};

export const Chip: React.FC<{ zh: string; en: string; style?: React.CSSProperties; dark?: boolean }> = ({ zh, en, style, dark }) => (
  <div style={{ position: 'absolute', display: 'flex', alignItems: 'baseline', gap: 12, padding: '14px 26px', borderRadius: 999, background: dark ? C.green : '#fff', color: dark ? '#fff' : C.ink, boxShadow: '0 14px 34px #142b1b24', whiteSpace: 'nowrap', ...style }}>
    <span style={{ font: `700 34px ${ZH}` }}>{zh}</span>
    <span style={{ font: `500 24px ${EN}`, color: dark ? '#a9d6bd' : C.muted }}>{en}</span>
  </div>
);

export type Line = { zh: string; en: string; file: string; seconds: number; start: number };

/** Bilingual subtitles: Chinese on top, English below, one sentence at a time. */
export const Subtitles: React.FC<{ lines: Line[]; dark?: boolean }> = ({ lines }) => {
  const t = useTime();
  const line = lines.find(l => t >= l.start - 0.1 && t < l.start + l.seconds + 0.25);
  if (!line) return null;
  const k = ramp(t, line.start - 0.1, 0.2) * (1 - ramp(t, line.start + line.seconds + 0.05, 0.2));
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 46 }}>
      <div style={{ opacity: k, transform: `translateY(${(1 - k) * 12}px)`, maxWidth: 1640, padding: '18px 40px 20px', borderRadius: 22, background: '#0f1d16d9', textAlign: 'center', boxShadow: '0 12px 40px #0004' }}>
        <div style={{ font: `700 ${Math.min(50, Math.floor(1540 / [...line.zh].length))}px/1.3 ${ZH}`, color: '#fff', letterSpacing: '0.02em', whiteSpace: 'nowrap' }}>{line.zh}</div>
        <div style={{ font: `500 32px/1.35 ${EN}`, color: '#bfe3cf', marginTop: 6 }}>{line.en}</div>
      </div>
    </AbsoluteFill>
  );
};
