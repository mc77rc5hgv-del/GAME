import Phaser from 'phaser';
import { GAME_CONFIG } from '../config/gameConfig';
import { WEAPONS } from '../config/weapons';
import { t, getLang } from '../localization';
import { scaleDisplayToHeight } from '../utils/physicsUtils';
import type { HeldWeaponState } from '../entities/Player';

const HP_BAR_WIDTH = 132;
const PORTRAIT_SIZE = 42;

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

    this.p1HpBar = this.buildPlayerPanel(1, 14, locale.menu.player1, '#4fc3f7', 0x4fc3f7);
    this.p2HpBar = this.buildPlayerPanel(2, w - 14, locale.menu.player2, '#ff6b6b', 0xff6b6b);

    // Score sits in its own small pill, low enough to clear the corner panels.
    const scorePill = this.add.graphics();
    scorePill.fillStyle(0x0a0a12, 0.55);
    scorePill.fillRoundedRect(w / 2 - 84, 10, 168, 34, 17);
    const crownP1 = this.add.image(w / 2 - 46, 27, 'icon_crown_p1').setOrigin(1, 0.5);
    crownP1.setDisplaySize((crownP1.width / crownP1.height) * 18, 18);
    const crownP2 = this.add.image(w / 2 + 46, 27, 'icon_crown_p2').setOrigin(0, 0.5);
    crownP2.setDisplaySize((crownP2.width / crownP2.height) * 18, 18);

    this.scoreText = this.add
      .text(w / 2, 27, '', { fontFamily: 'monospace', fontSize: '18px', color: '#ffe066', fontStyle: 'bold' })
      .setOrigin(0.5);

    this.muteHint = this.add
      .text(w / 2, 52, '', { fontFamily: 'monospace', fontSize: '13px', color: '#8a83a8' })
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
    this.p1HpBar.width = HP_BAR_WIDTH * hpRatio1;
    this.p2HpBar.width = HP_BAR_WIDTH * hpRatio2;

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

  /**
   * Compact arcade panel: a small portrait chip (the character's own idle
   * art, not a generic icon) + name + a slim HP bar + weapon/ammo line, all
   * inside one small rounded pill instead of the old large black rectangle.
   * `side` mirrors the whole layout so P2's panel reads right-to-left,
   * portrait hugging the screen edge on both sides.
   */
  private buildPlayerPanel(
    playerIndex: 1 | 2,
    edgeX: number,
    name: string,
    colorCss: string,
    colorHex: number
  ): Phaser.GameObjects.Rectangle {
    const side: 'left' | 'right' = playerIndex === 1 ? 'left' : 'right';
    const panelW = 208;
    const panelH = 52;
    const panelX = side === 'left' ? edgeX : edgeX - panelW;
    const portraitCX = side === 'left' ? panelX + 30 : panelX + panelW - 30;
    const barInnerX = side === 'left' ? portraitCX + 30 : portraitCX - 30;

    const bg = this.add.graphics();
    bg.fillStyle(0x0a0a12, 0.5);
    bg.fillRoundedRect(panelX, 10, panelW, panelH, 14);
    bg.lineStyle(1.5, colorHex, 0.5);
    bg.strokeRoundedRect(panelX, 10, panelW, panelH, 14);

    const portraitR = PORTRAIT_SIZE / 2 + 3;
    const portraitBg = this.add.circle(portraitCX, 36, portraitR, colorHex, 0.18);
    portraitBg.setStrokeStyle(2, colorHex, 0.8);

    const portrait = this.add.image(portraitCX, 40, `player${playerIndex}_idle`);
    scaleDisplayToHeight(portrait, PORTRAIT_SIZE);
    const maskShape = this.make.graphics({});
    maskShape.fillStyle(0xffffff);
    maskShape.fillCircle(portraitCX, 36, portraitR - 1);
    portrait.setMask(maskShape.createGeometryMask());

    this.add
      .text(portraitCX, 10 + panelH + 4, name, { fontFamily: 'monospace', fontSize: '11px', color: colorCss })
      .setOrigin(0.5, 0)
      .setAlpha(0.85);

    const barOriginX = side === 'left' ? barInnerX : barInnerX - HP_BAR_WIDTH;
    this.add.rectangle(barOriginX, 24, HP_BAR_WIDTH, 10, 0x2a2440).setOrigin(0, 0.5);
    const hpBar = this.add
      .rectangle(side === 'left' ? barInnerX : barInnerX, 24, HP_BAR_WIDTH, 10, colorHex)
      .setOrigin(side === 'left' ? 0 : 1, 0.5);

    const weaponText = this.add
      .text(side === 'left' ? barInnerX : barInnerX, 34, '', {
        fontFamily: 'monospace',
        fontSize: '12px',
        color: '#d8d4ea',
      })
      .setOrigin(side === 'left' ? 0 : 1, 0);

    if (playerIndex === 1) this.p1WeaponText = weaponText;
    else this.p2WeaponText = weaponText;

    return hpBar;
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
