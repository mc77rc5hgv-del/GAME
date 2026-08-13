import Phaser from 'phaser';
import { GAME_CONFIG } from '../config/gameConfig';
import { PHYSICS_CONFIG } from '../config/physicsConfig';
import { Player } from '../entities/Player';
import { WeaponPickup } from '../entities/Weapon';
import { Projectile } from '../entities/Projectile';
import { DestructionSystem, type TileRect } from '../systems/DestructionSystem';
import { ExplosionSystem } from '../systems/ExplosionSystem';
import { WeaponSystem } from '../systems/WeaponSystem';
import { SpawnManager, type WeaponSpawnPoint } from '../systems/SpawnManager';
import { RoundManager, type WorldBounds } from '../systems/RoundManager';
import type { InputManager } from '../systems/InputManager';
import type { AudioManager } from '../systems/AudioManager';

const ARENA_RECTS: TileRect[] = [
  { x: 800, y: 620, width: 640, height: 120 },
  { x: 300, y: 480, width: 280, height: 40 },
  { x: 1300, y: 480, width: 280, height: 40 },
  { x: 550, y: 300, width: 160, height: 40 },
  { x: 1050, y: 300, width: 160, height: 40 },
];

const WEAPON_SPAWN_POINTS: WeaponSpawnPoint[] = [
  { x: 800, y: 540 },
  { x: 300, y: 440 },
  { x: 1300, y: 440 },
  { x: 550, y: 260 },
  { x: 1050, y: 260 },
];

const P1_SPAWN = { x: 650, y: 460 };
const P2_SPAWN = { x: 950, y: 460 };

export class GameScene extends Phaser.Scene {
  private inputManager!: InputManager;
  private audio!: AudioManager;
  private bus!: Phaser.Events.EventEmitter;

  private players!: [Player, Player];
  private destruction!: DestructionSystem;
  private explosionSystem!: ExplosionSystem;
  private weaponSystem!: WeaponSystem;
  private spawnManager!: SpawnManager;
  private roundManager!: RoundManager;

  private manualPaused = false;
  private focusPaused = false;
  private debugEnabled = false;
  private debugGraphics!: Phaser.GameObjects.Graphics;

  private camCenterX = GAME_CONFIG.WORLD_WIDTH / 2;
  private camCenterY = GAME_CONFIG.WORLD_HEIGHT / 2;
  private camZoom = 1;

  constructor() {
    super('GameScene');
  }

  create(): void {
    this.inputManager = this.registry.get('input');
    this.audio = this.registry.get('audio');
    this.bus = this.registry.get('bus');

    this.manualPaused = false;
    this.focusPaused = false;
    this.debugEnabled = false;

    this.matter.world.setGravity(0, PHYSICS_CONFIG.GRAVITY);

    this.destruction = new DestructionSystem(this);
    this.destruction.buildFromRects(ARENA_RECTS);

    this.players = [new Player(this, P1_SPAWN.x, P1_SPAWN.y, 1), new Player(this, P2_SPAWN.x, P2_SPAWN.y, 2)];

    this.explosionSystem = new ExplosionSystem(this, this.destruction, {
      onCameraShake: (intensity, duration) =>
        this.cameras.main.shake(duration, Phaser.Math.Clamp(intensity * 0.014, 0.003, 0.024)),
    });

    this.weaponSystem = new WeaponSystem(this, this.explosionSystem, this.audio);
    this.weaponSystem.setPlayers(this.players);

    this.spawnManager = new SpawnManager(this, this.weaponSystem);
    this.spawnManager.setPoints(WEAPON_SPAWN_POINTS);
    // Armed lazily on the first update() tick - see SpawnManager for why
    // this.time.now can't be trusted this early (inside Scene.create()).

    const bounds: WorldBounds = {
      minX: -PHYSICS_CONFIG.KILL_BOUNDS_MARGIN,
      maxX: GAME_CONFIG.WORLD_WIDTH + PHYSICS_CONFIG.KILL_BOUNDS_MARGIN,
      killY: GAME_CONFIG.WORLD_HEIGHT + PHYSICS_CONFIG.KILL_BOUNDS_MARGIN,
    };
    this.roundManager = new RoundManager(this, bounds);
    this.roundManager.on('roundEnd', (payload: unknown) => {
      this.audio.play('roundWin');
      this.bus.emit('round:end', payload);
    });
    this.roundManager.on('matchEnd', (payload: unknown) => this.bus.emit('match:end', payload));
    this.roundManager.on('roundRestart', () => this.restartRound());

    this.cameras.main.setBackgroundColor(0x14101d);
    this.camCenterX = (P1_SPAWN.x + P2_SPAWN.x) / 2;
    this.camCenterY = (P1_SPAWN.y + P2_SPAWN.y) / 2;
    this.camZoom = GAME_CONFIG.CAMERA.MAX_ZOOM;
    this.drawBackdrop();

    this.debugGraphics = this.add.graphics().setDepth(1000);

    this.matter.world.on('collisionstart', this.handleCollisionStart, this);

    this.bus.on('ui:resume', this.togglePause, this);
    this.bus.on('ui:restartRound', () => this.restartRound(), this);
    this.bus.on('ui:playAgain', () => {
      this.roundManager.resetMatch();
      this.restartRound();
    });
    this.bus.on('ui:mainMenu', () => {
      this.scene.stop('UIScene');
      this.scene.start('MenuScene');
    });

    this.audio.startMusic();

    this.scene.launch('UIScene');
    this.bus.emit('game:started', { scoreP1: this.roundManager.scoreP1, scoreP2: this.roundManager.scoreP2 });

    this.events.once(Phaser.Scenes.Events.SHUTDOWN, this.cleanup, this);
  }

  private drawBackdrop(): void {
    const g = this.add.graphics().setDepth(-10).setScrollFactor(0.3);
    g.fillStyle(0x1c1830, 1);
    g.fillRect(-2000, -2000, GAME_CONFIG.WORLD_WIDTH + 4000, GAME_CONFIG.WORLD_HEIGHT + 4000);
    for (let i = 0; i < 40; i++) {
      g.fillStyle(0x2a2440, 1);
      g.fillCircle(
        Phaser.Math.Between(-500, GAME_CONFIG.WORLD_WIDTH + 500),
        Phaser.Math.Between(-500, GAME_CONFIG.WORLD_HEIGHT + 200),
        Phaser.Math.Between(1, 3)
      );
    }
  }

  setExternalPause(paused: boolean): void {
    this.focusPaused = paused;
    this.applyPauseState();
  }

  private togglePause(): void {
    this.manualPaused = !this.manualPaused;
    this.applyPauseState();
  }

  private applyPauseState(): void {
    const paused = this.manualPaused || this.focusPaused;
    if (paused) {
      this.matter.world.pause();
    } else {
      this.matter.world.resume();
    }
    this.bus.emit('pause:changed', { paused, manual: this.manualPaused });
  }

  update(time: number, delta: number): void {
    if (this.inputManager.debugTogglePressed()) {
      this.debugEnabled = !this.debugEnabled;
      this.bus.emit('debug:toggled', this.debugEnabled);
      if (!this.debugEnabled) this.debugGraphics.clear();
    }
    if (this.inputManager.pausePressed()) {
      this.togglePause();
    }

    const paused = this.manualPaused || this.focusPaused;
    if (paused) {
      if (this.debugEnabled) this.renderDebug();
      else this.debugGraphics.clear();
      return;
    }

    if (this.inputManager.musicTogglePressed()) {
      const muted = this.audio.toggleMusic();
      this.bus.emit('music:changed', muted);
    }

    if (this.roundManager.roundActive) {
      const p1Input = this.inputManager.getPlayer1Input();
      const p2Input = this.inputManager.getPlayer2Input();
      this.players[0].setInput(p1Input);
      this.players[1].setInput(p2Input);

      this.updateGrounded(this.players[0], this.players[1]);
      this.updateGrounded(this.players[1], this.players[0]);

      for (const player of this.players) {
        player.update(time, delta);
        if (player.justJumped) {
          this.audio.play('jump');
          player.justJumped = false;
        }
      }

      this.handleFireAndInteract(this.players[0], time);
      this.handleFireAndInteract(this.players[1], time);
    }

    this.weaponSystem.update(time, PHYSICS_CONFIG.GRAVITY);
    this.spawnManager.update(time);
    this.roundManager.checkDeaths(this.players);
    this.updateCamera();
    this.emitHud();

    if (this.debugEnabled) this.renderDebug();
    else this.debugGraphics.clear();
  }

  private handleFireAndInteract(player: Player, time: number): void {
    if (!player.alive) return;
    if (player.controls.interactPressed) {
      this.weaponSystem.handleInteract(player);
    }
    if (player.controls.fireHeld) {
      this.weaponSystem.tryFire(player, time);
    }
  }

  private updateGrounded(player: Player, otherPlayer: Player): void {
    const halfHeight = PHYSICS_CONFIG.PLAYER_HEIGHT / 2;
    const halfWidth = PHYSICS_CONFIG.PLAYER_WIDTH / 2;
    const bodies = [...this.destruction.getAllBodies(), otherPlayer.body as MatterJS.BodyType];
    const offsets = [-(halfWidth - 5), 0, halfWidth - 5];
    let grounded = false;
    for (const offsetX of offsets) {
      const start = { x: player.x + offsetX, y: player.y + halfHeight - 4 };
      const end = { x: player.x + offsetX, y: player.y + halfHeight + 6 };
      const collisions = this.matter.query.ray(bodies, start, end);
      if (collisions.length > 0) {
        grounded = true;
        break;
      }
    }
    player.applyGroundedFromRay(grounded, this.time.now);
  }

  private handleCollisionStart(event: Phaser.Physics.Matter.Events.CollisionStartEvent): void {
    for (const pair of event.pairs) {
      this.resolvePair(pair.bodyA, pair.bodyB);
    }
  }

  private resolvePair(bodyA: MatterJS.BodyType, bodyB: MatterJS.BodyType): void {
    const goA = bodyA.gameObject as Phaser.GameObjects.GameObject | null;
    const goB = bodyB.gameObject as Phaser.GameObjects.GameObject | null;

    const projectile = goA instanceof Projectile ? goA : goB instanceof Projectile ? goB : null;
    if (projectile) {
      const other = projectile === goA ? goB : goA;
      if (other instanceof Player) {
        this.weaponSystem.handleProjectileHitPlayer(projectile, other);
      } else if (!(other instanceof WeaponPickup)) {
        this.weaponSystem.handleProjectileHitTerrain(projectile);
      }
      return;
    }

    const weapon = goA instanceof WeaponPickup ? goA : goB instanceof WeaponPickup ? goB : null;
    if (weapon) {
      const other = weapon === goA ? goB : goA;
      if (other instanceof Player) {
        this.weaponSystem.handleWeaponHitPlayer(weapon, other);
      }
    }
  }

  private restartRound(): void {
    this.weaponSystem.clear();
    this.destruction.buildFromRects(ARENA_RECTS);
    this.players[0].resetForRound(P1_SPAWN.x, P1_SPAWN.y);
    this.players[1].resetForRound(P2_SPAWN.x, P2_SPAWN.y);
    this.spawnManager.reset(this.time.now);
    this.roundManager.startRound();
    this.bus.emit('round:restart', { scoreP1: this.roundManager.scoreP1, scoreP2: this.roundManager.scoreP2 });
  }

  private updateCamera(): void {
    const cam = this.cameras.main;
    const [p1, p2] = this.players;
    const midX = (p1.x + p2.x) / 2;
    const midY = (p1.y + p2.y) / 2;
    const dist = Phaser.Math.Distance.Between(p1.x, p1.y, p2.x, p2.y);

    const targetZoom = Phaser.Math.Clamp(
      (GAME_CONFIG.BASE_WIDTH - GAME_CONFIG.CAMERA.PADDING) / Math.max(dist, 260),
      GAME_CONFIG.CAMERA.MIN_ZOOM,
      GAME_CONFIG.CAMERA.MAX_ZOOM
    );

    this.camZoom = Phaser.Math.Linear(this.camZoom, targetZoom, GAME_CONFIG.CAMERA.ZOOM_SMOOTH);
    this.camCenterX = Phaser.Math.Linear(this.camCenterX, midX, GAME_CONFIG.CAMERA.PAN_SMOOTH);
    this.camCenterY = Phaser.Math.Linear(this.camCenterY, midY, GAME_CONFIG.CAMERA.PAN_SMOOTH);

    cam.setZoom(this.camZoom);
    cam.centerOn(this.camCenterX, this.camCenterY);
  }

  private emitHud(): void {
    this.bus.emit('hud:update', {
      p1: { hp: this.players[0].health, weapon: this.players[0].currentWeapon, alive: this.players[0].alive },
      p2: { hp: this.players[1].health, weapon: this.players[1].currentWeapon, alive: this.players[1].alive },
      scoreP1: this.roundManager.scoreP1,
      scoreP2: this.roundManager.scoreP2,
    });
  }

  private renderDebug(): void {
    const g = this.debugGraphics;
    g.clear();
    g.lineStyle(1, 0x00ff88, 0.9);
    for (const body of this.destruction.getAllBodies()) {
      const b = body.bounds;
      g.strokeRect(b.min.x, b.min.y, b.max.x - b.min.x, b.max.y - b.min.y);
    }
    for (const player of this.players) {
      if (!player.body) continue;
      const b = (player.body as MatterJS.BodyType).bounds;
      g.lineStyle(1, 0xffcc00, 1);
      g.strokeRect(b.min.x, b.min.y, b.max.x - b.min.x, b.max.y - b.min.y);
    }
    for (const w of this.weaponSystem.weaponsOnField) {
      if (!w.body) continue;
      const b = (w.body as MatterJS.BodyType).bounds;
      g.lineStyle(1, 0x66aaff, 1);
      g.strokeRect(b.min.x, b.min.y, b.max.x - b.min.x, b.max.y - b.min.y);
    }
    for (const proj of this.weaponSystem.projectiles) {
      if (!proj.body) continue;
      const b = (proj.body as MatterJS.BodyType).bounds;
      g.lineStyle(1, 0xff4477, 1);
      g.strokeRect(b.min.x, b.min.y, b.max.x - b.min.x, b.max.y - b.min.y);
    }

    this.bus.emit('debug:update', {
      fps: Math.round(this.game.loop.actualFps),
      bodyCount: this.matter.world.getAllBodies().length,
      p1: this.debugPlayerInfo(this.players[0]),
      p2: this.debugPlayerInfo(this.players[1]),
      projectiles: this.weaponSystem.projectiles.length,
      weapons: this.weaponSystem.weaponsOnField.length,
      tiles: this.destruction.tileCount,
    });
  }

  private debugPlayerInfo(player: Player) {
    const body = player.body as MatterJS.BodyType | undefined;
    return {
      vx: body ? Math.round(body.velocity.x * 100) / 100 : 0,
      vy: body ? Math.round(body.velocity.y * 100) / 100 : 0,
      grounded: player.grounded,
      weapon: player.currentWeapon?.type ?? 'none',
      ammo: player.currentWeapon?.ammo ?? 0,
      hp: Math.round(player.health),
    };
  }

  private cleanup(): void {
    this.matter.world.off('collisionstart', this.handleCollisionStart, this);
    this.bus.off('ui:resume', this.togglePause, this);
    this.bus.removeAllListeners('ui:restartRound');
    this.bus.removeAllListeners('ui:playAgain');
    this.bus.removeAllListeners('ui:mainMenu');
    this.roundManager.removeAllListeners();
    this.audio.stopMusic();
    this.players.forEach((p) => p.destroyAttachments());
  }
}
