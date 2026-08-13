export type SfxKey =
  | 'jump'
  | 'pickup'
  | 'throw'
  | 'pistol'
  | 'shotgun'
  | 'rifle'
  | 'rocket'
  | 'grenade'
  | 'explosion'
  | 'hit'
  | 'roundWin'
  | 'uiClick';

/**
 * Synthesizes all SFX procedurally via WebAudio so the prototype has real
 * audio feedback without needing binary asset files yet. The event API
 * (play/muted/pause on blur) is what the rest of the game depends on, so
 * swapping in real samples later is a drop-in change inside this file only.
 */
export class AudioManager {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private musicGain: GainNode | null = null;
  private musicNodes: { osc: OscillatorNode; lfo: OscillatorNode }[] = [];
  private _muted = false;
  private _musicMuted = false;
  private suspendedByFocus = false;

  init(): void {
    if (this.ctx) return;
    try {
      const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AudioCtx();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.value = this._muted ? 0 : 0.55;
      this.masterGain.connect(this.ctx.destination);
      this.musicGain = this.ctx.createGain();
      this.musicGain.gain.value = this._musicMuted ? 0 : 0.16;
      this.musicGain.connect(this.masterGain);
    } catch (e) {
      console.warn('AudioManager: WebAudio unavailable', e);
    }
  }

  /** Soft ambient pad - simple by design; swap for a real music asset later. */
  startMusic(): void {
    if (!this.ctx || !this.musicGain || this.musicNodes.length > 0) return;
    const baseFreqs = [110, 164.81, 220];
    for (const freq of baseFreqs) {
      const osc = this.ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.value = freq;
      const lfo = this.ctx.createOscillator();
      lfo.type = 'sine';
      lfo.frequency.value = 0.05 + Math.random() * 0.05;
      const lfoGain = this.ctx.createGain();
      lfoGain.gain.value = 4;
      lfo.connect(lfoGain);
      lfoGain.connect(osc.frequency);
      const voiceGain = this.ctx.createGain();
      voiceGain.gain.value = 0.2;
      osc.connect(voiceGain);
      voiceGain.connect(this.musicGain);
      osc.start();
      lfo.start();
      this.musicNodes.push({ osc, lfo });
    }
  }

  stopMusic(): void {
    for (const { osc, lfo } of this.musicNodes) {
      osc.stop();
      lfo.stop();
    }
    this.musicNodes = [];
  }

  get musicMuted(): boolean {
    return this._musicMuted;
  }

  toggleMusic(): boolean {
    this._musicMuted = !this._musicMuted;
    if (this.musicGain) {
      this.musicGain.gain.value = this._musicMuted ? 0 : 0.16;
    }
    return this._musicMuted;
  }

  private resumeIfNeeded(): void {
    if (this.ctx && this.ctx.state === 'suspended' && !this.suspendedByFocus) {
      this.ctx.resume().catch(() => undefined);
    }
  }

  get muted(): boolean {
    return this._muted;
  }

  setMuted(muted: boolean): void {
    this._muted = muted;
    if (this.masterGain) {
      this.masterGain.gain.value = muted ? 0 : 0.55;
    }
  }

  toggleMuted(): boolean {
    this.setMuted(!this._muted);
    return this._muted;
  }

  suspend(): void {
    if (this.ctx && this.ctx.state === 'running') {
      this.suspendedByFocus = true;
      this.ctx.suspend().catch(() => undefined);
    }
  }

  resume(): void {
    if (this.ctx) {
      this.suspendedByFocus = false;
      this.ctx.resume().catch(() => undefined);
    }
  }

  play(key: SfxKey): void {
    if (!this.ctx || !this.masterGain || this._muted) return;
    this.resumeIfNeeded();
    const ctx = this.ctx;
    const now = ctx.currentTime;

    switch (key) {
      case 'jump':
        this.tone(220, 420, 0.09, 'sine', now);
        break;
      case 'pickup':
        this.tone(520, 880, 0.08, 'triangle', now);
        break;
      case 'throw':
        this.tone(300, 180, 0.08, 'sawtooth', now);
        break;
      case 'pistol':
        this.noiseBurst(0.05, 900, now);
        break;
      case 'shotgun':
        this.noiseBurst(0.14, 500, now);
        break;
      case 'rifle':
        this.noiseBurst(0.045, 1100, now);
        break;
      case 'rocket':
        this.noiseBurst(0.22, 260, now);
        break;
      case 'grenade':
        this.noiseBurst(0.12, 340, now);
        break;
      case 'explosion':
        this.explosionSound(now);
        break;
      case 'hit':
        this.tone(140, 90, 0.07, 'square', now);
        break;
      case 'roundWin':
        this.tone(440, 880, 0.35, 'triangle', now);
        break;
      case 'uiClick':
        this.tone(600, 600, 0.04, 'square', now);
        break;
    }
  }

  private tone(freqStart: number, freqEnd: number, duration: number, type: OscillatorType, now: number): void {
    if (!this.ctx || !this.masterGain) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freqStart, now);
    osc.frequency.linearRampToValueAtTime(freqEnd, now + duration);
    gain.gain.setValueAtTime(0.35, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
    osc.connect(gain);
    gain.connect(this.masterGain);
    osc.start(now);
    osc.stop(now + duration + 0.02);
  }

  private noiseBurst(duration: number, filterFreq: number, now: number): void {
    if (!this.ctx || !this.masterGain) return;
    const bufferSize = Math.floor(this.ctx.sampleRate * duration);
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = filterFreq;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0.5, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.masterGain);
    noise.start(now);
    noise.stop(now + duration);
  }

  private explosionSound(now: number): void {
    this.noiseBurst(0.5, 220, now);
    this.tone(90, 40, 0.4, 'sine', now);
  }
}
