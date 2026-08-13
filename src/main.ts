import Phaser from 'phaser';
import { GAME_CONFIG } from './config/gameConfig';
import { initYandexSDK } from './platform/YandexSDK';
import { setLang } from './localization';
import { InputManager } from './systems/InputManager';
import { AudioManager } from './systems/AudioManager';
import { BootScene } from './scenes/BootScene';
import { MenuScene } from './scenes/MenuScene';
import { GameScene } from './scenes/GameScene';
import { UIScene } from './scenes/UIScene';

async function bootstrap(): Promise<void> {
  // Platform requirement 2.14: language MUST be auto-detected from the
  // Yandex SDK at startup, before anything is rendered.
  const platform = await initYandexSDK();
  setLang(platform.lang);

  const inputManager = new InputManager();
  const audioManager = new AudioManager();
  const bus = new Phaser.Events.EventEmitter();

  const config: Phaser.Types.Core.GameConfig = {
    type: Phaser.AUTO,
    parent: 'game-root',
    backgroundColor: '#14101d',
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
      width: GAME_CONFIG.BASE_WIDTH,
      height: GAME_CONFIG.BASE_HEIGHT,
    },
    physics: {
      default: 'matter',
      matter: {
        gravity: { x: 0, y: 0 },
        debug: false,
      },
    },
    scene: [BootScene, MenuScene, GameScene, UIScene],
  };

  const game = new Phaser.Game(config);
  (window as unknown as { __game: Phaser.Game }).__game = game;
  game.registry.set('platform', platform);
  game.registry.set('input', inputManager);
  game.registry.set('audio', audioManager);
  game.registry.set('bus', bus);

  // Edge-triggered input state ("was this key just pressed") is cleared once
  // per rendered frame, after every scene has had a chance to read it.
  game.events.on(Phaser.Core.Events.POST_STEP, () => inputManager.endFrame());

  function setGamePaused(paused: boolean): void {
    if (paused) audioManager.suspend();
    else audioManager.resume();

    const gameScene = game.scene.getScene('GameScene') as GameScene | null;
    if (gameScene && gameScene.scene.isActive()) {
      gameScene.setExternalPause(paused);
    }
  }

  document.addEventListener('visibilitychange', () => setGamePaused(document.hidden));
  window.addEventListener('blur', () => setGamePaused(true));
  window.addEventListener('focus', () => {
    if (!document.hidden) setGamePaused(false);
  });
}

bootstrap().catch((err) => {
  console.error('Failed to bootstrap game', err);
});
