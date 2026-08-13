import Phaser from 'phaser';
import { GAME_CONFIG } from '../config/gameConfig';
import { Player } from '../entities/Player';

export interface RoundEndPayload {
  winnerIndex: 1 | 2;
  scoreP1: number;
  scoreP2: number;
}

export interface MatchEndPayload {
  winnerIndex: 1 | 2;
  scoreP1: number;
  scoreP2: number;
}

export interface WorldBounds {
  minX: number;
  maxX: number;
  killY: number;
}

/**
 * Owns match score and the round life cycle: detects a player's death (HP
 * depleted or falling out of the arena), applies a short slow-motion freeze,
 * announces the winner, then signals a round or match restart.
 */
export class RoundManager extends Phaser.Events.EventEmitter {
  private scene: Phaser.Scene;
  private bounds: WorldBounds;
  scoreP1 = 0;
  scoreP2 = 0;
  roundActive = true;
  matchOver = false;

  constructor(scene: Phaser.Scene, bounds: WorldBounds) {
    super();
    this.scene = scene;
    this.bounds = bounds;
  }

  setBounds(bounds: WorldBounds): void {
    this.bounds = bounds;
  }

  resetMatch(): void {
    this.scoreP1 = 0;
    this.scoreP2 = 0;
    this.matchOver = false;
    this.roundActive = true;
  }

  startRound(): void {
    this.roundActive = true;
  }

  checkDeaths(players: [Player, Player]): void {
    if (!this.roundActive) return;
    for (const player of players) {
      if (!player.alive) continue;
      const outOfBounds =
        player.y > this.bounds.killY || player.x < this.bounds.minX || player.x > this.bounds.maxX;
      if (player.health <= 0 || outOfBounds) {
        const winner: 1 | 2 = player.playerIndex === 1 ? 2 : 1;
        this.endRound(winner, players.find((p) => p !== player)!);
        return;
      }
    }
  }

  private endRound(winnerIndex: 1 | 2, winnerPlayer: Player): void {
    this.roundActive = false;
    if (winnerIndex === 1) this.scoreP1++;
    else this.scoreP2++;

    this.applyTimeScale(GAME_CONFIG.ROUND_END_SLOWMO_TIME_SCALE);

    const payload: RoundEndPayload = { winnerIndex, scoreP1: this.scoreP1, scoreP2: this.scoreP2 };
    this.emit('roundEnd', payload);
    void winnerPlayer;

    this.scene.time.delayedCall(GAME_CONFIG.ROUND_END_FREEZE_MS, () => {
      this.applyTimeScale(1);

      if (this.scoreP1 >= GAME_CONFIG.ROUNDS_TO_WIN || this.scoreP2 >= GAME_CONFIG.ROUNDS_TO_WIN) {
        this.matchOver = true;
        const matchPayload: MatchEndPayload = {
          winnerIndex: this.scoreP1 > this.scoreP2 ? 1 : 2,
          scoreP1: this.scoreP1,
          scoreP2: this.scoreP2,
        };
        this.emit('matchEnd', matchPayload);
      } else {
        this.scene.time.delayedCall(
          Math.max(0, GAME_CONFIG.ROUND_RESTART_DELAY_MS - GAME_CONFIG.ROUND_END_FREEZE_MS),
          () => this.emit('roundRestart')
        );
      }
    });
  }

  private applyTimeScale(scale: number): void {
    this.scene.time.timeScale = scale;
    const matterScene = this.scene as unknown as { matter?: Phaser.Physics.Matter.MatterPhysics };
    if (matterScene.matter) {
      matterScene.matter.world.engine.timing.timeScale = scale;
    }
  }
}
