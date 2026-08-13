import type { PlayerInputState } from '../entities/Player';

/**
 * All bindings use KeyboardEvent.code (physical key position), not
 * KeyboardEvent.key, so a Cyrillic/AZERTY/etc layout never breaks controls -
 * "KeyA" is always the key physically where A sits on a US QWERTY layout.
 */
const P1_KEYS = {
  left: 'KeyA',
  right: 'KeyD',
  jump: 'KeyW',
  down: 'KeyS',
  interact: 'KeyE',
  fire: 'KeyR',
} as const;

const P2_KEYS = {
  left: 'ArrowLeft',
  right: 'ArrowRight',
  jump: 'ArrowUp',
  down: 'ArrowDown',
  interact: 'KeyL',
  fire: 'KeyK',
} as const;

export const MUSIC_KEY = 'KeyM';
export const PAUSE_KEY = 'Escape';
export const DEBUG_KEY = 'Backquote';

const ALL_MAPPED_CODES = new Set<string>([
  ...Object.values(P1_KEYS),
  ...Object.values(P2_KEYS),
  MUSIC_KEY,
  PAUSE_KEY,
  DEBUG_KEY,
  'Space',
]);

/**
 * Tracks raw physical key state for the whole app lifetime (constructed once
 * in main.ts) and derives per-player input snapshots on demand. Also owns
 * preventDefault() for every mapped key so arrows/space never scroll the page.
 */
export class InputManager {
  private down = new Set<string>();
  private pressedThisFrame = new Set<string>();
  private oneShotConsumers = 0;

  constructor() {
    window.addEventListener('keydown', this.onKeyDown, { passive: false });
    window.addEventListener('keyup', this.onKeyUp, { passive: false });
    window.addEventListener('blur', this.onBlur);
    window.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  private onKeyDown = (e: KeyboardEvent): void => {
    if (ALL_MAPPED_CODES.has(e.code)) {
      e.preventDefault();
    }
    if (!this.down.has(e.code)) {
      this.pressedThisFrame.add(e.code);
    }
    this.down.add(e.code);
  };

  private onKeyUp = (e: KeyboardEvent): void => {
    if (ALL_MAPPED_CODES.has(e.code)) {
      e.preventDefault();
    }
    this.down.delete(e.code);
  };

  private onBlur = (): void => {
    this.down.clear();
    this.pressedThisFrame.clear();
  };

  isDown(code: string): boolean {
    return this.down.has(code);
  }

  wasPressed(code: string): boolean {
    return this.pressedThisFrame.has(code);
  }

  getPlayer1Input(): PlayerInputState {
    return {
      left: this.isDown(P1_KEYS.left),
      right: this.isDown(P1_KEYS.right),
      jump: this.isDown(P1_KEYS.jump),
      jumpPressed: this.wasPressed(P1_KEYS.jump),
      down: this.isDown(P1_KEYS.down),
      interactPressed: this.wasPressed(P1_KEYS.interact),
      fireHeld: this.isDown(P1_KEYS.fire),
    };
  }

  getPlayer2Input(): PlayerInputState {
    return {
      left: this.isDown(P2_KEYS.left),
      right: this.isDown(P2_KEYS.right),
      jump: this.isDown(P2_KEYS.jump),
      jumpPressed: this.wasPressed(P2_KEYS.jump),
      down: this.isDown(P2_KEYS.down),
      interactPressed: this.wasPressed(P2_KEYS.interact),
      fireHeld: this.isDown(P2_KEYS.fire),
    };
  }

  musicTogglePressed(): boolean {
    return this.wasPressed(MUSIC_KEY);
  }

  pausePressed(): boolean {
    return this.wasPressed(PAUSE_KEY);
  }

  debugTogglePressed(): boolean {
    return this.wasPressed(DEBUG_KEY);
  }

  /**
   * Must be called exactly once per rendered frame, after every scene/system
   * has had a chance to read this frame's edge-triggered ("pressed") state.
   */
  endFrame(): void {
    this.pressedThisFrame.clear();
  }

  destroy(): void {
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    window.removeEventListener('blur', this.onBlur);
  }
}
