import { resolveSupportedLang, type SupportedLang } from '../localization';

/**
 * Minimal surface of the Yandex Games SDK that this game depends on.
 * Matches the real SDK's shape (https://yandex.ru/dev/games/doc/en/sdk/sdk-about)
 * closely enough that MockYandexSDK is a drop-in replacement during local dev.
 */
export interface YandexSDKLike {
  environment: {
    i18n: { lang: string };
  };
  features: {
    LoadingAPI: { ready: () => void };
    GameplayAPI: { start: () => void; stop: () => void };
  };
  adv: {
    showFullscreenAdv: (opts?: { callbacks?: Record<string, () => void> }) => void;
  };
  getPlayer: () => Promise<unknown>;
}

class MockYandexSDK implements YandexSDKLike {
  environment = {
    i18n: { lang: MockYandexSDK.detectMockLang() },
  };
  features = {
    LoadingAPI: {
      ready: () => console.info('[YandexSDK:mock] LoadingAPI.ready()'),
    },
    GameplayAPI: {
      start: () => console.info('[YandexSDK:mock] GameplayAPI.start()'),
      stop: () => console.info('[YandexSDK:mock] GameplayAPI.stop()'),
    },
  };
  adv = {
    showFullscreenAdv: (opts?: { callbacks?: Record<string, () => void> }) => {
      console.info('[YandexSDK:mock] showFullscreenAdv() - skipped in dev');
      opts?.callbacks?.onClose?.();
    },
  };
  async getPlayer(): Promise<unknown> {
    return null;
  }

  /**
   * Local dev has no real SDK to read language from, so we use the browser's
   * language as a best-effort mock signal only. In production the real SDK's
   * environment.i18n.lang is always used instead (see initYandexSDK below).
   */
  private static detectMockLang(): string {
    return navigator.language ?? 'en';
  }
}

declare global {
  interface Window {
    YaGames?: { init: () => Promise<YandexSDKLike> };
  }
}

function waitForRealSdk(timeoutMs: number): Promise<YandexSDKLike | null> {
  return new Promise((resolve) => {
    const start = performance.now();
    const poll = () => {
      if (window.YaGames) {
        window.YaGames
          .init()
          .then((sdk) => resolve(sdk))
          .catch(() => resolve(null));
        return;
      }
      if (performance.now() - start >= timeoutMs) {
        resolve(null);
        return;
      }
      requestAnimationFrame(poll);
    };
    poll();
  });
}

export interface PlatformSDK {
  sdk: YandexSDKLike;
  lang: SupportedLang;
  isMock: boolean;
}

let cached: PlatformSDK | null = null;

/**
 * Initializes the Yandex Games SDK. On yandex.ru/games hosting the real SDK
 * script (loaded in index.html) attaches window.YaGames almost immediately.
 * Outside that environment (local dev, CI, other hosting) it never appears,
 * so we time out quickly and fall back to a safe mock that never blocks
 * startup.
 *
 * Platform requirement 2.14: language MUST be read automatically from
 * ysdk.environment.i18n.lang at startup, not from navigator.language.
 */
export async function initYandexSDK(): Promise<PlatformSDK> {
  if (cached) return cached;

  const real = await waitForRealSdk(2500);
  const sdk = real ?? new MockYandexSDK();
  const lang = resolveSupportedLang(sdk.environment.i18n.lang);

  cached = { sdk, lang, isMock: real === null };
  return cached;
}

export function getPlatformSDK(): PlatformSDK | null {
  return cached;
}
