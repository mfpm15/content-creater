export type Shot = {
  id: string; startFrame: number; endFrame: number; title: string; subject: string;
  diagram?: {kind: 'process' | 'comparison'; labels: string[]};
  family: 'process' | 'data' | 'comparison' | 'concept';
  camera: 'legacy' | 'locked' | 'push-in' | 'pull-out' | 'pan-left' | 'pan-right' | 'orbit';
  strength: number; lighting: 'legacy' | 'soft' | 'dramatic'; transition: 'legacy' | 'fade' | 'cut' | 'slide';
};
export type StudioProps = {
  version: 1; width: number; height: number; fps: 30 | 60; totalFrames: number;
  topic: string; brand: {background: string; accent: string; text: string; wordmark: string; font: string};
  shots: Shot[]; captions: {startFrame: number; endFrame: number; text: string}[];
};
