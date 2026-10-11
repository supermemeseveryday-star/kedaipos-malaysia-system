import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Backdrop, Box, BrowserShot, C, Chip, EN, Line, Phone, Tap, ZH, ramp, usePop, useTime } from './ui';

type SceneProps = { lines: Line[]; seconds: number };

// Screenshot coordinates below are fractions of the 1440×900 app screenshots in docs/screenshots.

export const Overview: React.FC<SceneProps> = ({ lines }) => {
  const t = useTime();
  const split = ramp(t, lines[1].start - 0.3, 1.0);
  const width = 1240 - 240 * split;
  const left = 340 - 200 * split;
  const top = 40 + 100 * split;
  const phoneIn = usePop(lines[1].start + 0.3);
  const free = usePop(lines[0].start + 4.2);
  const open = usePop(lines[0].start + 3.4);
  const link = ramp(t, lines[1].start + 1.0, 1.2);
  return (
    <AbsoluteFill>
      <Backdrop />
      <BrowserShot src="02-checkout.png" width={width} left={left} top={top}
        shots={[{ at: 0, x: 0.5, y: 0.5, scale: 1 }, { at: lines[1].start - 0.3, x: 0.5, y: 0.5, scale: 1.06 }, { at: lines[1].start + 0.7, x: 0.5, y: 0.5, scale: 1 }]} />
      <Chip zh="开源" en="Open source" dark style={{ left: 1480 - 300 * split, top: 70, transform: `scale(${open * (1 - split)})` }} />
      <Chip zh="免费" en="Free" style={{ left: 1560 - 300 * split, top: 160, transform: `scale(${free * (1 - split)})` }} />
      {/* The shop computer talks to staff phones over the shop Wi-Fi */}
      <svg width="420" height="300" viewBox="0 0 420 300" style={{ position: 'absolute', left: 1080, top: 300, opacity: link }}>
        <path d="M20 200 C 140 40, 280 40, 400 200" fill="none" stroke={C.green} strokeWidth="6" strokeDasharray="14 14" strokeDashoffset={-t * 60} />
        <g transform="translate(210 70)">
          <circle r="48" fill="#fff" stroke={C.mint} strokeWidth="6" />
          <path d="M-26 -4 Q0 -28 26 -4" fill="none" stroke={C.green} strokeWidth="7" strokeLinecap="round" />
          <path d="M-14 9 Q0 -4 14 9" fill="none" stroke={C.green} strokeWidth="7" strokeLinecap="round" />
          <circle cy="22" r="6" fill={C.green} />
        </g>
      </svg>
      <Phone src="12-phone-zh.png" left={1440 + (1 - phoneIn) * 600} top={130} height={660} />
      <Chip zh="店里的电脑" en="Shop computer" style={{ left: 140, top: 34, opacity: ramp(t, lines[1].start + 1.2, 0.5) }} />
      <Chip zh="手机 · 平板" en="Phone · Tablet" style={{ left: 1400, top: 34, opacity: ramp(t, lines[1].start + 1.6, 0.5) }} />
    </AbsoluteFill>
  );
};

export const Checkout: React.FC<SceneProps> = ({ lines }) => {
  const [a, b] = [lines[0].start, lines[1].start];
  return (
    <AbsoluteFill>
      <Backdrop />
      <BrowserShot src="02-checkout.png" shots={[
        { at: 0, x: 0.5, y: 0.5, scale: 1 },
        { at: a + 0.5, x: 0.62, y: 0.5, scale: 1.3 },
        { at: b - 0.2, x: 0.62, y: 0.5, scale: 1.3 },
        { at: b + 0.5, x: 0.33, y: 0.12, scale: 1.9 },
      ]}>
        <Tap x={0.662} y={0.756} at={a + 1.0} />
        <Tap x={0.313} y={0.756} at={a + 1.8} />
        <Box x0={0.70} y0={0.19} x1={0.982} y1={0.795} at={a + 2.1} until={b} />
        <Box x0={0.168} y0={0.188} x1={0.408} y1={0.242} at={b + 0.8} until={b + 3.0} />
        <Tap x={0.324} y={0.214} at={b + 1.5} />
        <Box x0={0.168} y0={0.012} x1={0.584} y1={0.068} at={b + 2.9} />
      </BrowserShot>
    </AbsoluteFill>
  );
};

export const Payment: React.FC<SceneProps> = ({ lines }) => {
  const t = useTime();
  const b = lines[1].start;
  const swap = ramp(t, b - 0.3, 0.5);
  return (
    <AbsoluteFill>
      <Backdrop />
      <BrowserShot src="03-cash-payment.png" opacity={1 - swap} shots={[{ at: 0, x: 0.5, y: 0.5, scale: 1 }, { at: 0.9, x: 0.5, y: 0.5, scale: 1.45 }]}>
        <Box x0={0.33} y0={0.545} x1={0.67} y1={0.595} at={1.8} />
      </BrowserShot>
      <BrowserShot src="04-qr-payment.png" opacity={swap} shots={[{ at: b - 0.3, x: 0.5, y: 0.5, scale: 1 }, { at: b + 0.5, x: 0.5, y: 0.5, scale: 1.45 }]}>
        <Box x0={0.405} y0={0.352} x1={0.595} y1={0.652} at={b + 1.0} until={b + 2.4} />
        <Box x0={0.33} y0={0.62} x1={0.67} y1={0.678} at={b + 2.3} />
      </BrowserShot>
    </AbsoluteFill>
  );
};

export const Receipt: React.FC<SceneProps> = ({ lines }) => {
  const t = useTime();
  const a = lines[0].start;
  const swap = ramp(t, a + 2.0, 0.5);
  return (
    <AbsoluteFill>
      <Backdrop />
      <BrowserShot src="05-orders.png" opacity={1 - swap} shots={[{ at: 0, x: 0.5, y: 0.35, scale: 1 }, { at: 1.2, x: 0.7, y: 0.6, scale: 1.3 }]}>
        <Tap x={0.856} y={0.752} at={a + 1.5} />
      </BrowserShot>
      <BrowserShot src="06-receipt.png" opacity={swap} shots={[{ at: a + 2.0, x: 0.5, y: 0.5, scale: 1.05 }, { at: a + 2.8, x: 0.5, y: 0.52, scale: 1.4 }]}>
        <Box x0={0.33} y0={0.645} x1={0.67} y1={0.702} at={a + 3.6} />
      </BrowserShot>
    </AbsoluteFill>
  );
};

export const Owner: React.FC<SceneProps> = ({ lines }) => {
  const t = useTime();
  const b = lines[1].start;
  const swap = ramp(t, b - 0.4, 0.5);
  return (
    <AbsoluteFill>
      <Backdrop />
      <BrowserShot src="07-products.png" opacity={1 - swap} shots={[{ at: 0, x: 0.5, y: 0.3, scale: 1.0 }, { at: b, x: 0.62, y: 0.55, scale: 1.2 }]}>
        <Box x0={0.62} y0={0.24} x1={0.86} y1={0.955} at={lines[0].start + 1.6} />
      </BrowserShot>
      <BrowserShot src="10-reports.png" opacity={swap} shots={[{ at: b - 0.4, x: 0.5, y: 0.3, scale: 1.0 }, { at: b + 0.4, x: 0.5, y: 0.28, scale: 1.22 }]}>
        <Box x0={0.168} y0={0.188} x1={0.982} y1={0.322} at={b + 0.8} until={b + 2.2} />
        <Box x0={0.576} y0={0.188} x1={0.778} y1={0.322} at={b + 2.2} color={C.gold} />
      </BrowserShot>
    </AbsoluteFill>
  );
};

const Feature: React.FC<{ zh: string; en: string; icon: 'lock' | 'offline'; at: number; top: number }> = ({ zh, en, icon, at, top }) => {
  const k = usePop(at);
  return (
    <div style={{ position: 'absolute', left: 1180, top, width: 600, padding: '30px 34px', borderRadius: 28, background: '#fff', boxShadow: '0 24px 60px #142b1b24', display: 'flex', gap: 28, alignItems: 'center', transform: `translateX(${(1 - k) * 160}px)`, opacity: Math.min(1, k * 1.5) }}>
      <svg width="92" height="92" viewBox="0 0 92 92" style={{ flex: '0 0 auto' }}>
        <rect width="92" height="92" rx="24" fill={C.mint} />
        {icon === 'lock' ? (
          <g fill="none" stroke={C.green} strokeWidth="6" strokeLinecap="round">
            <rect x="24" y="42" width="44" height="32" rx="7" fill={C.green} stroke="none" />
            <path d="M32 42 V33 a14 14 0 0 1 28 0 V42" />
          </g>
        ) : (
          <g fill="none" stroke={C.green} strokeWidth="6" strokeLinecap="round">
            <path d="M20 42 Q46 18 72 42" /><path d="M31 54 Q46 41 61 54" />
            <circle cx="46" cy="66" r="4" fill={C.green} />
            <path d="M22 22 L70 72" stroke={C.red} />
          </g>
        )}
      </svg>
      <div>
        <div style={{ font: `700 42px/1.25 ${ZH}`, color: C.ink }}>{zh}</div>
        <div style={{ font: `500 26px/1.4 ${EN}`, color: C.muted, marginTop: 4 }}>{en}</div>
      </div>
    </div>
  );
};

export const Anywhere: React.FC<SceneProps> = ({ lines }) => {
  const t = useTime();
  const [a, b] = [lines[0].start, lines[1].start];
  const shift = ramp(t, b - 0.2, 0.8);
  const langs: [string, string][] = [['中文', 'Chinese'], ['English', '英文'], ['Bahasa Melayu', '马来文']];
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: 'absolute', inset: 0, transform: `translateX(${-330 * shift}px)` }}>
        <Phone src="12-phone-zh.png" left={760} top={50} height={720} style={{ transform: 'rotate(-4deg)' }} />
        <Phone src="13-phone-cart-zh.png" left={1110} top={70} height={720} style={{ transform: 'rotate(4deg)' }} />
      </div>
      {langs.map(([zh, en], i) => {
        const k = usePop(a + 0.9 + i * 0.6);
        return <Chip key={zh} zh={zh} en={en} dark={i === 0} style={{ left: 250, top: 200 + i * 150, transform: `scale(${k})`, opacity: 1 - shift }} />;
      })}
      <Feature zh="数据保存在本机" en="Your data stays on your computer" icon="lock" at={b + 0.3} top={190} />
      <Feature zh="断网照常收银" en="Keeps working offline" icon="offline" at={b + 2.6} top={450} />
    </AbsoluteFill>
  );
};
