import Phaser from 'phaser';
import { PHYSICS_CONFIG } from '../config/physicsConfig';
import { GAME_CONFIG } from '../config/gameConfig';
import type { WeaponType } from '../config/weapons';
import { WEAPONS } from '../config/weapons';
import { applyImpulse, scaleDisplayToHeight, scaleDisplayToWidth } from '../utils/physicsUtils';

export type FacingDirection = 1 | -1;

export interface PlayerInputState {
  left: boolean;
  right: boolean;
  jump: boolean;
  jumpPressed: boolean;
  down: boolean;
  interactPressed: boolean;
  fireHeld: boolean;
}

export interface HeldWeaponState {
  type: WeaponType;
  ammo: number;
}

export const PLAYER_COLORS: Record<1 | 2, number> = {
  1: 0x4fc3f7,
  2: 0xff6b6b,
};

type AnimState = 'idle' | 'run' | 'jump' | 'fall' | 'crouch' | 'hit' | 'knockout';

const RUN_FRAME_MS = 110;
const RUN_FRAMES = ['run_0', 'run_1', 'run_2'];
const MOVE_ANIM_SPEED_THRESHOLD = 0.6;
const VERTICAL_ANIM_SPEED_THRESHOLD = 0.6;

const emptyInput = (): PlayerInputState => ({
  left: false,
  right: false,
  jump: false,
  jumpPressed: false,
  down: false,
  interactPressed: false,
  fireHeld: false,
});

export class Player extends Phaser.Physics.Matter.Sprite {
  readonly playerIndex: 1 | 2;
  health: number = GAME_CONFIG.PLAYER_MAX_HP;
  facing: FacingDirection = 1;
  grounded = false;
  private lastGroundedAt = -Infinity;
  private jumpBufferedAt = -Infinity;
  knockbackUntil = 0;
  currentWeapon: HeldWeaponState | null = null;
  alive = true;
  lastFireAt = -Infinity;
  justJumped = false;
  /** Named `controls` (not `input`) to avoid colliding with Phaser GameObject's own `input` (pointer interactivity). */
  controls: PlayerInputState = emptyInput();

  /** The real on-screen body art. Bottom-center anchored to the physics
   * body's feet line, scaled independently of the collision box, so the
   * visual size and the hitbox never have to match. `this` (the Matter
   * sprite) stays invisible and physics-only. */
  private visualSprite: Phaser.GameObjects.Image;
  private shadow: Phaser.GameObjects.Ellipse;
  weaponSprite: Phaser.GameObjects.Image;
  private nameLabel: Phaser.GameObjects.Text;
  private hpBarBg: Phaser.GameObjects.Rectangle;
  private hpBarFill: Phaser.GameObjects.Rectangle;

  private animState: AnimState = 'idle';
  private animChangedAt = 0;

  constructor(scene: Phaser.Scene, x: number, y: number, playerIndex: 1 | 2) {
    super(scene.matter.world, x, y, `player${playerIndex}_idle`, undefined, {
      label: `player${playerIndex}`,
    });
    this.playerIndex = playerIndex;
    scene.add.existing(this);
    this.setVisible(false);

    this.setRectangle(PHYSICS_CONFIG.PLAYER_WIDTH, PHYSICS_CONFIG.PLAYER_HEIGHT, {
      chamfer: { radius: 6 },
    });
    this.setFixedRotation();
    this.setFriction(PHYSICS_CONFIG.PLAYER_FRICTION, undefined, PHYSICS_CONFIG.PLAYER_FRICTION_AIR);
    this.setBounce(PHYSICS_CONFIG.PLAYER_RESTITUTION);
    this.setMass(PHYSICS_CONFIG.PLAYER_MASS);
    this.setCollisionCategory(GAME_CONFIG.COLLISION.PLAYER);
    this.setCollidesWith([
      GAME_CONFIG.COLLISION.GROUND,
      GAME_CONFIG.COLLISION.PLAYER,
      GAME_CONFIG.COLLISION.WEAPON,
      GAME_CONFIG.COLLISION.PROJECTILE,
      GAME_CONFIG.COLLISION.DEBRIS,
    ]);

    this.shadow = scene.add.ellipse(x, y, 34, 10, 0x000000, 0.38);
    this.shadow.setDepth(4);

    this.visualSprite = scene.add.image(x, y, `player${playerIndex}_idle`);
    this.visualSprite.setOrigin(0.5, 1);
    this.visualSprite.setDepth(10);
    scaleDisplayToHeight(this.visualSprite, PHYSICS_CONFIG.PLAYER_SPRITE_HEIGHT);

    this.weaponSprite = scene.add.image(x, y, 'weapon_pistol');
    this.weaponSprite.setVisible(false);
    this.weaponSprite.setDepth(11);

    this.nameLabel = scene.add
      .text(x, y - 56, `P${playerIndex}`, {
        fontFamily: 'monospace',
        fontSize: '14px',
        color: playerIndex === 1 ? '#4fc3f7' : '#ff6b6b',
      })
      .setOrigin(0.5)
      .setDepth(12);

    this.hpBarBg = scene.add.rectangle(x, y - 44, 50, 6, 0x1a1a1a).setDepth(12);
    this.hpBarFill = scene.add.rectangle(x - 25, y - 44, 50, 6, playerIndex === 1 ? 0x4fc3f7 : 0xff6b6b).setOrigin(0, 0.5).setDepth(13);
  }

  setInput(input: PlayerInputState): void {
    this.controls = input;
  }

  get isStunned(): boolean {
    return this.scene.time.now < this.knockbackUntil;
  }

  applyGroundedFromRay(grounded: boolean, time: number): void {
    this.grounded = grounded;
    if (grounded) {
      this.lastGroundedAt = time;
    }
  }

  update(time: number, _delta: number): void {
    if (!this.alive || !this.body) return;
    const cfg = PHYSICS_CONFIG;
    const body = this.body as MatterJS.BodyType;
    const stunned = this.isStunned;

    if (this.controls.jumpPressed) this.jumpBufferedAt = time;

    if (!stunned) {
      const inAir = !this.grounded;
      const controlMul = inAir ? cfg.AIR_CONTROL : 1;
      const duckMul = this.controls.down && this.grounded ? cfg.DUCK_SPEED_MULTIPLIER : 1;

      let moveDir = 0;
      if (this.controls.left) moveDir -= 1;
      if (this.controls.right) moveDir += 1;

      if (moveDir !== 0) {
        this.facing = moveDir > 0 ? 1 : -1;
        const currentSpeed = body.velocity.x;
        const movingWithInput = Math.sign(currentSpeed) === moveDir || currentSpeed === 0;
        if (!movingWithInput || Math.abs(currentSpeed) < cfg.MAX_SPEED * duckMul) {
          this.applyForce(new Phaser.Math.Vector2(cfg.MOVE_FORCE * moveDir * controlMul * duckMul, 0));
        }
      } else if (this.grounded) {
        this.setVelocityX(body.velocity.x * (1 - cfg.GROUND_FRICTION));
      } else {
        this.setVelocityX(body.velocity.x * cfg.AIR_FRICTION);
      }

      if (Math.abs(body.velocity.x) > cfg.MAX_SPEED * 1.4) {
        this.setVelocityX(Phaser.Math.Clamp(body.velocity.x, -cfg.MAX_SPEED * 1.4, cfg.MAX_SPEED * 1.4));
      }

      if (this.controls.down && !this.grounded && body.velocity.y > 0) {
        this.applyForce(new Phaser.Math.Vector2(0, cfg.GRAVITY * 0.001 * (cfg.FAST_FALL_MULTIPLIER - 1)));
      }

      const withinBuffer = time - this.jumpBufferedAt <= cfg.JUMP_BUFFER_MS;
      const withinCoyote = time - this.lastGroundedAt <= cfg.COYOTE_TIME_MS;
      if (withinBuffer && (this.grounded || withinCoyote)) {
        applyImpulse(this, 0, -cfg.JUMP_FORCE);
        this.jumpBufferedAt = -Infinity;
        this.lastGroundedAt = -Infinity;
        this.grounded = false;
        this.justJumped = true;
      }
    }

    this.updateAnimState(time);
    this.updateAttachments(time);
  }

  /** Picks the current pose purely from physics state - never a fixed timer. */
  private updateAnimState(time: number): void {
    const body = this.body as MatterJS.BodyType;
    let next: AnimState;

    if (this.isStunned) {
      next = 'hit';
    } else if (!this.grounded && body.velocity.y < -VERTICAL_ANIM_SPEED_THRESHOLD) {
      next = 'jump';
    } else if (!this.grounded && body.velocity.y > VERTICAL_ANIM_SPEED_THRESHOLD) {
      next = 'fall';
    } else if (this.grounded && this.controls.down) {
      next = 'crouch';
    } else if (this.grounded && Math.abs(body.velocity.x) > MOVE_ANIM_SPEED_THRESHOLD) {
      next = 'run';
    } else {
      next = 'idle';
    }

    if (next !== this.animState) {
      this.animState = next;
      this.animChangedAt = time;
    }
  }

  private currentPoseTexture(time: number): string {
    if (this.animState === 'run') {
      const idx = Math.floor((time - this.animChangedAt) / RUN_FRAME_MS) % RUN_FRAMES.length;
      return `player${this.playerIndex}_${RUN_FRAMES[idx]}`;
    }
    return `player${this.playerIndex}_${this.animState}`;
  }

  private updateAttachments(time: number): void {
    const x = this.x;
    const y = this.y;
    const feetY = y + PHYSICS_CONFIG.PLAYER_HEIGHT / 2;
    const headTopY = feetY - PHYSICS_CONFIG.PLAYER_SPRITE_HEIGHT;

    this.nameLabel.setPosition(x, headTopY - 12);
    this.hpBarBg.setPosition(x, headTopY);
    this.hpBarFill.setPosition(x - 25, headTopY);
    const hpRatio = Phaser.Math.Clamp(this.health / GAME_CONFIG.PLAYER_MAX_HP, 0, 1);
    this.hpBarFill.width = 50 * hpRatio;
    this.hpBarFill.fillColor = hpRatio > 0.5 ? (this.playerIndex === 1 ? 0x4fc3f7 : 0xff6b6b) : hpRatio > 0.25 ? 0xffb020 : 0xff3b3b;

    this.shadow.setPosition(x, feetY + 2);

    const textureKey = this.currentPoseTexture(time);
    if (this.visualSprite.texture.key !== textureKey) {
      this.visualSprite.setTexture(textureKey);
      scaleDisplayToHeight(this.visualSprite, PHYSICS_CONFIG.PLAYER_SPRITE_HEIGHT);
    }
    this.visualSprite.setPosition(x, feetY);
    this.visualSprite.setFlipX(this.facing === -1);

    if (this.currentWeapon) {
      const def = WEAPONS[this.currentWeapon.type];
      const att = def.attachment;
      const textureKeyWeapon = `weapon_${this.currentWeapon.type}`;
      if (this.weaponSprite.texture.key !== textureKeyWeapon) {
        this.weaponSprite.setTexture(textureKeyWeapon);
        scaleDisplayToWidth(this.weaponSprite, att.displayWidth);
      }
      this.weaponSprite.setPosition(x + att.offsetX * this.facing, y + att.offsetY);
      this.weaponSprite.setFlipX(this.facing === -1);
      this.weaponSprite.setRotation(att.rotation * this.facing);
      this.weaponSprite.setVisible(true);
      this.weaponSprite.setDepth(11);
    } else {
      this.weaponSprite.setVisible(false);
    }
  }

  getMuzzlePosition(): { x: number; y: number } {
    if (!this.currentWeapon) return { x: this.x + 20 * this.facing, y: this.y };
    const att = WEAPONS[this.currentWeapon.type].attachment;
    return {
      x: this.x + att.muzzleOffsetX * this.facing,
      y: this.y + att.muzzleOffsetY,
    };
  }

  takeDamage(amount: number): void {
    if (!this.alive) return;
    this.health = Math.max(0, this.health - amount);
  }

  applyKnockback(impulseX: number, impulseY: number): void {
    applyImpulse(this, impulseX, impulseY);
    this.knockbackUntil = Math.max(
      this.knockbackUntil,
      this.scene.time.now + PHYSICS_CONFIG.MIN_KNOCKBACK_STUN_MS
    );
  }

  resetForRound(x: number, y: number): void {
    this.health = GAME_CONFIG.PLAYER_MAX_HP;
    this.alive = true;
    this.currentWeapon = null;
    this.knockbackUntil = 0;
    this.jumpBufferedAt = -Infinity;
    this.lastGroundedAt = -Infinity;
    this.animState = 'idle';
    this.animChangedAt = this.scene.time.now;
    this.setPosition(x, y);
    this.setVelocity(0, 0);
    this.visualSprite.setVisible(true);
    this.visualSprite.setAlpha(1);
    this.shadow.setVisible(true);
    (this.body as MatterJS.BodyType).collisionFilter.mask =
      GAME_CONFIG.COLLISION.GROUND |
      GAME_CONFIG.COLLISION.PLAYER |
      GAME_CONFIG.COLLISION.WEAPON |
      GAME_CONFIG.COLLISION.PROJECTILE |
      GAME_CONFIG.COLLISION.DEBRIS;
    this.updateAttachments(this.scene.time.now);
  }

  /** Eliminated but stays visible lying down (knockout pose) through the
   * round-end freeze - only the physics interaction actually stops. */
  markEliminated(): void {
    this.alive = false;
    this.animState = 'knockout';
    this.visualSprite.setTexture(`player${this.playerIndex}_knockout`);
    scaleDisplayToHeight(this.visualSprite, PHYSICS_CONFIG.PLAYER_SPRITE_HEIGHT * 0.7);
    this.visualSprite.setPosition(this.x, this.y + PHYSICS_CONFIG.PLAYER_HEIGHT / 2);
    this.weaponSprite.setVisible(false);
    this.setVelocity(0, 0);
    (this.body as MatterJS.BodyType).collisionFilter.mask = 0;
  }

  destroyAttachments(): void {
    this.nameLabel.destroy();
    this.hpBarBg.destroy();
    this.hpBarFill.destroy();
    this.weaponSprite.destroy();
    this.visualSprite.destroy();
    this.shadow.destroy();
  }
}
