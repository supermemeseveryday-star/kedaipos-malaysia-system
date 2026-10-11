import React from 'react';
import { Composition } from 'remotion';
import { FPS, KedaiPosIntro, totalFrames } from './Video';

export const Root: React.FC = () => (
  <Composition id="KedaiPosIntro" component={KedaiPosIntro} durationInFrames={totalFrames} fps={FPS} width={1920} height={1080} />
);
