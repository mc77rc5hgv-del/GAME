import Phaser from 'phaser';
import { t } from '../localization';
import type { AudioManager } from '../systems/AudioManager';
import type { PlatformSDK } from '../platform/YandexSDK';

/**
 * Main menu / controls screen. Yandex requirement 2.14 + GameReady: this is
 * the first fully interactive screen, so LoadingAPI.ready() is fired here
 * once the menu has actually finished rendering - never via a bare timeout.
 */
export class MenuScene extends Phaser.Scene {
  private readyCalled = false;

  constructor() {
    super('MenuScene');
  }

  create(): void {
    const audio = this.registry.get('audio') as AudioManager;
    audio.init();

    const { width, height } = this.scale;
    const cx = width / 2;
    const locale = t();

    this.cameras.main.setBackgroundColor(0x14101d);

    this.add
      .text(cx, height * 0.14, locale.menu.title, {
        fontFamily: 'monospace',
        fontSize: '52px',
        color: '#ffe066',
        fontStyle: 'bold',
      })
      .setOrigin(0.5);

    this.add
      .text(cx, height * 0.14 + 52, locale.menu.subtitle, {
        fontFamily: 'monospace',
        fontSize: '18px',
        color: '#a9a2c8',
      })
      .setOrigin(0.5);

    this.buildControlsColumn(cx - 260, height * 0.32, locale.menu.player1, '#4fc3f7', [
      [locale.menu.move, 'A / D'],
      [locale.menu.jump, 'W'],
      [locale.menu.duck, 'S'],
      [locale.menu.interact, 'E'],
      [locale.menu.fire, 'R'],
    ]);

    this.buildControlsColumn(cx + 260, height * 0.32, locale.menu.player2, '#ff6b6b', [
      [locale.menu.move, '← / →'],
      [locale.menu.jump, '↑'],
      [locale.menu.duck, '↓'],
      [locale.menu.interact, 'L'],
      [locale.menu.fire, 'K'],
    ]);

    this.add
      .text(cx, height * 0.74, `${locale.menu.toggleMusic}: M      ${locale.menu.pause}: Esc`, {
        fontFamily: 'monospace',
        fontSize: '15px',
        color: '#8a83a8',
      })
      .setOrigin(0.5);

    const startBtn = this.add
      .text(cx, height * 0.85, locale.menu.start, {
        fontFamily: 'monospace',
        fontSize: '30px',
        color: '#0a0a12',
        backgroundColor: '#ffe066',
        padding: { x: 34, y: 14 },
      })
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true });

    startBtn.on('pointerover', () => startBtn.setBackgroundColor('#fff2a8'));
    startBtn.on('pointerout', () => startBtn.setBackgroundColor('#ffe066'));
    startBtn.on('pointerdown', () => {
      audio.resume();
      audio.play('uiClick');
      this.scene.start('GameScene');
    });

    this.input.keyboard?.once('keydown-SPACE', () => {
      audio.resume();
      audio.play('uiClick');
      this.scene.start('GameScene');
    });

    this.signalGameReady();
  }

  private buildControlsColumn(
    x: number,
    y: number,
    title: string,
    color: string,
    rows: [string, string][]
  ): void {
    this.add
      .text(x, y, title, { fontFamily: 'monospace', fontSize: '22px', color, fontStyle: 'bold' })
      .setOrigin(0.5);

    const locale = t();
    this.add
      .text(x, y + 30, locale.menu.controlsTitle, { fontFamily: 'monospace', fontSize: '13px', color: '#8a83a8' })
      .setOrigin(0.5);

    rows.forEach(([label, key], i) => {
      const rowY = y + 60 + i * 26;
      this.add
        .text(x - 90, rowY, `${label}:`, { fontFamily: 'monospace', fontSize: '15px', color: '#d8d4ea' })
        .setOrigin(0, 0.5);
      this.add
        .text(x + 90, rowY, key, { fontFamily: 'monospace', fontSize: '15px', color: '#ffe066' })
        .setOrigin(1, 0.5);
    });
  }

  /**
   * Fires ysdk.features.LoadingAPI.ready() exactly once, only after this
   * scene (the game's first real, interactive screen) has finished building
   * its display list - satisfying the platform's GameReady requirements.
   */
  private signalGameReady(): void {
    if (this.readyCalled) return;
    this.readyCalled = true;
    const platform = this.registry.get('platform') as PlatformSDK | undefined;
    if (!platform) return;
    try {
      platform.sdk.features.LoadingAPI.ready();
    } catch (e) {
      console.warn('LoadingAPI.ready() failed', e);
    }
  }
}
