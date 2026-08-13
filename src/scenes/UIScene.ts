import Phaser from 'phaser';
import { GAME_CONFIG } from '../config/gameConfig';
import { WEAPONS } from '../config/weapons';
import { t, getLang } from '../localization';
import type { HeldWeaponState } from '../entities/Player';

interface HudPayload {
  p1: { hp: number; weapon: HeldWeaponState | null; alive: boolean };
  p2: { hp: number; weapon: HeldWeaponState | null; alive: boolean };
  scoreP1: number;
  scoreP2: number;
}

interface DebugPayload {
  fps: number;
  bodyCount: number;
  projectiles: number;
  weapons: number;
  tiles: number;
  p1: Record<string, unknown>;
  p2: Record<string, unknown>;
}

export class UIScene extends Phaser.Scene {
  private bus!: Phaser.Events.EventEmitter;

  private p1HpBar!: Phaser.GameObjects.Rectangle;
  private p2HpBar!: Phaser.GameObjects.Rectangle;
  private p1WeaponText!: Phaser.GameObjects.Text;
  private p2WeaponText!: Phaser.GameObjects.Text;
  private scoreText!: Phaser.GameObjects.Text;

  private roundBanner!: Phaser.GameObjects.Container;
  private pauseOverlay!: Phaser.GameObjects.Container;
  private matchEndOverlay!: Phaser.GameObjects.Container;
  private debugText!: Phaser.GameObjects.Text;
  private muteHint!: Phaser.GameObjects.Text;

  constructor() {
    super({ key: 'UIScene', active: false });
  }

  create(): void {
    this.bus = this.registry.get('bus');
    const locale = t();
    const w = this.scale.width;

    this.add.rectangle(0, 0, 240, 74, 0x0a0a12, 0.55).setOrigin(0, 0).setPosition(16, 14);
    this.add.rectangle(0, 0, 240, 74, 0x0a0a12, 0.55).setOrigin(1, 0).setPosition(w - 16, 14);

    this.add.text(24, 20, locale.menu.player1, { fontFamily: 'monospace', fontSize: '14px', color: '#4fc3f7' });
    this.add.rectangle(24, 40, 200, 14, 0x2a2440).setOrigin(0, 0);
    this.p1HpBar = this.add.rectangle(24, 40, 200, 14, 0x4fc3f7).setOrigin(0, 0);
    this.p1WeaponText = this.add.text(24, 58, '', { fontFamily: 'monospace', fontSize: '13px', color: '#d8d4ea' });

    this.add
      .text(w - 24, 20, locale.menu.player2, { fontFamily: 'monospace', fontSize: '14px', color: '#ff6b6b' })
      .setOrigin(1, 0);
    this.add.rectangle(w - 24, 40, 200, 14, 0x2a2440).setOrigin(1, 0);
    this.p2HpBar = this.add.rectangle(w - 24, 40, 200, 14, 0xff6b6b).setOrigin(1, 0);
    this.p2WeaponText = this.add
      .text(w - 24, 58, '', { fontFamily: 'monospace', fontSize: '13px', color: '#d8d4ea' })
      .setOrigin(1, 0);

    this.scoreText = this.add
      .text(w / 2, 20, '', { fontFamily: 'monospace', fontSize: '20px', color: '#ffe066', fontStyle: 'bold' })
      .setOrigin(0.5, 0);

    this.muteHint = this.add
      .text(w / 2, 50, '', { fontFamily: 'monospace', fontSize: '13px', color: '#8a83a8' })
      .setOrigin(0.5, 0);

    this.debugText = this.add
      .text(16, this.scale.height - 16, '', {
        fontFamily: 'monospace',
        fontSize: '12px',
        color: '#66ff99',
        backgroundColor: '#0a0a12cc',
        padding: { x: 8, y: 6 },
      })
      .setOrigin(0, 1)
      .setVisible(false);

    this.roundBanner = this.buildRoundBanner();
    this.pauseOverlay = this.buildPauseOverlay();
    this.matchEndOverlay = this.buildMatchEndOverlay();

    this.bus.on('hud:update', this.onHudUpdate, this);
    this.bus.on('round:end', this.onRoundEnd, this);
    this.bus.on('round:restart', this.onRoundRestart, this);
    this.bus.on('match:end', this.onMatchEnd, this);
    this.bus.on('pause:changed', this.onPauseChanged, this);
    this.bus.on('music:changed', this.onMusicChanged, this);
    this.bus.on('debug:update', this.onDebugUpdate, this);
    this.bus.on('debug:toggled', this.onDebugToggled, this);

    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.bus.off('hud:update', this.onHudUpdate, this);
      this.bus.off('round:end', this.onRoundEnd, this);
      this.bus.off('round:restart', this.onRoundRestart, this);
      this.bus.off('match:end', this.onMatchEnd, this);
      this.bus.off('pause:changed', this.onPauseChanged, this);
      this.bus.off('music:changed', this.onMusicChanged, this);
      this.bus.off('debug:update', this.onDebugUpdate, this);
      this.bus.off('debug:toggled', this.onDebugToggled, this);
    });
  }

  private onHudUpdate = (payload: HudPayload): void => {
    const hpRatio1 = Phaser.Math.Clamp(payload.p1.hp / GAME_CONFIG.PLAYER_MAX_HP, 0, 1);
    const hpRatio2 = Phaser.Math.Clamp(payload.p2.hp / GAME_CONFIG.PLAYER_MAX_HP, 0, 1);
    this.p1HpBar.width = 200 * hpRatio1;
    this.p2HpBar.width = 200 * hpRatio2;

    this.p1WeaponText.setText(this.weaponLine(payload.p1.weapon));
    this.p2WeaponText.setText(this.weaponLine(payload.p2.weapon));

    this.scoreText.setText(`${payload.scoreP1}  :  ${payload.scoreP2}`);
  };

  private weaponLine(weapon: HeldWeaponState | null): string {
    const locale = t();
    if (!weapon) return locale.hud.unarmed;
    const def = WEAPONS[weapon.type];
    const name = getLang() === 'ru' ? def.displayName.ru : def.displayName.en;
    return `${name}  ${weapon.ammo}/${def.maxAmmo}`;
  }

  private buildRoundBanner(): Phaser.GameObjects.Container {
    const w = this.scale.width;
    const h = this.scale.height;
    const text = this.add
      .text(0, 0, '', {
        fontFamily: 'monospace',
        fontSize: '44px',
        color: '#ffe066',
        fontStyle: 'bold',
        align: 'center',
      })
      .setOrigin(0.5);
    const container = this.add.container(w / 2, h / 2, [text]).setDepth(200);
    container.setVisible(false);
    container.setData('text', text);
    return container;
  }

  private onRoundEnd = (payload: { winnerIndex: 1 | 2; scoreP1: number; scoreP2: number }): void => {
    const locale = t();
    const text = this.roundBanner.getData('text') as Phaser.GameObjects.Text;
    text.setText(`${locale.menu[`player${payload.winnerIndex}` as 'player1' | 'player2']} ${locale.round.wins}`);
    this.roundBanner.setVisible(true);
    this.roundBanner.setAlpha(1);
  };

  private onRoundRestart = (): void => {
    this.roundBanner.setVisible(false);
  };

  private buildPauseOverlay(): Phaser.GameObjects.Container {
    const w = this.scale.width;
    const h = this.scale.height;
    const locale = t();
    const bg = this.add.rectangle(0, 0, w, h, 0x000000, 0.6).setOrigin(0);
    const title = this.add
      .text(w / 2, h * 0.32, locale.pause.title, { fontFamily: 'monospace', fontSize: '40px', color: '#ffe066' })
      .setOrigin(0.5);

    const resumeBtn = this.makeButton(w / 2, h * 0.48, locale.pause.resume, () => this.bus.emit('ui:resume'));
    const restartBtn = this.makeButton(w / 2, h * 0.58, locale.pause.restart, () => {
      this.bus.emit('ui:resume');
      this.bus.emit('ui:restartRound');
    });
    const menuBtn = this.makeButton(w / 2, h * 0.68, locale.pause.menu, () => this.bus.emit('ui:mainMenu'));

    const container = this.add.container(0, 0, [bg, title, resumeBtn, restartBtn, menuBtn]).setDepth(210);
    container.setVisible(false);
    return container;
  }

  private buildMatchEndOverlay(): Phaser.GameObjects.Container {
    const w = this.scale.width;
    const h = this.scale.height;
    const locale = t();
    const bg = this.add.rectangle(0, 0, w, h, 0x000000, 0.72).setOrigin(0);
    const title = this.add
      .text(w / 2, h * 0.34, '', { fontFamily: 'monospace', fontSize: '42px', color: '#ffe066', fontStyle: 'bold' })
      .setOrigin(0.5);
    const scoreLine = this.add
      .text(w / 2, h * 0.44, '', { fontFamily: 'monospace', fontSize: '20px', color: '#d8d4ea' })
      .setOrigin(0.5);

    const playAgainBtn = this.makeButton(w / 2, h * 0.58, locale.end.playAgain, () => {
      this.matchEndOverlay.setVisible(false);
      this.bus.emit('ui:playAgain');
    });
    const menuBtn = this.makeButton(w / 2, h * 0.68, locale.end.mainMenu, () => this.bus.emit('ui:mainMenu'));

    const container = this.add
      .container(0, 0, [bg, title, scoreLine, playAgainBtn, menuBtn])
      .setDepth(220);
    container.setData('title', title);
    container.setData('scoreLine', scoreLine);
    container.setVisible(false);
    return container;
  }

  private onMatchEnd = (payload: { winnerIndex: 1 | 2; scoreP1: number; scoreP2: number }): void => {
    const locale = t();
    const title = this.matchEndOverlay.getData('title') as Phaser.GameObjects.Text;
    const scoreLine = this.matchEndOverlay.getData('scoreLine') as Phaser.GameObjects.Text;
    title.setText(`${locale.menu[`player${payload.winnerIndex}` as 'player1' | 'player2']} ${locale.round.matchWinner}`);
    scoreLine.setText(`${payload.scoreP1} : ${payload.scoreP2}`);
    this.matchEndOverlay.setVisible(true);
  };

  private makeButton(x: number, y: number, label: string, onClick: () => void): Phaser.GameObjects.Text {
    const btn = this.add
      .text(x, y, label, {
        fontFamily: 'monospace',
        fontSize: '22px',
        color: '#0a0a12',
        backgroundColor: '#ffe066',
        padding: { x: 24, y: 10 },
      })
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true });
    btn.on('pointerover', () => btn.setBackgroundColor('#fff2a8'));
    btn.on('pointerout', () => btn.setBackgroundColor('#ffe066'));
    btn.on('pointerdown', onClick);
    return btn;
  }

  private onPauseChanged = (payload: { paused: boolean }): void => {
    this.pauseOverlay.setVisible(payload.paused);
  };

  private onMusicChanged = (muted: boolean): void => {
    const locale = t();
    this.muteHint.setText(muted ? `♪ ${locale.menu.toggleMusic}: OFF` : '');
    this.tweens.add({ targets: this.muteHint, alpha: { from: 1, to: 0 }, delay: 900, duration: 600 });
  };

  private onDebugToggled = (enabled: boolean): void => {
    this.debugText.setVisible(enabled);
  };

  private onDebugUpdate = (data: DebugPayload): void => {
    if (!this.debugText.visible) return;
    const lines = [
      `FPS: ${data.fps}`,
      `bodies: ${data.bodyCount}  tiles: ${data.tiles}`,
      `proj: ${data.projectiles}  weapons: ${data.weapons}`,
      `P1 vx:${data.p1.vx} vy:${data.p1.vy} grounded:${data.p1.grounded} wpn:${data.p1.weapon} ammo:${data.p1.ammo} hp:${data.p1.hp}`,
      `P2 vx:${data.p2.vx} vy:${data.p2.vy} grounded:${data.p2.grounded} wpn:${data.p2.weapon} ammo:${data.p2.ammo} hp:${data.p2.hp}`,
    ];
    this.debugText.setText(lines.join('\n'));
  };

}
