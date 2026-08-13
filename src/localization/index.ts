import { en } from './en';
import { ru } from './ru';
import type { LocaleShape } from './en';

export type SupportedLang = 'ru' | 'en';

const LOCALES: Record<SupportedLang, LocaleShape> = { en, ru };

/**
 * Maps any SDK/browser language code to a supported locale.
 * Requirement 2.14: only ru/en are localized, everything else falls back to en.
 */
export function resolveSupportedLang(rawLang: string | null | undefined): SupportedLang {
  if (!rawLang) return 'en';
  const normalized = rawLang.toLowerCase().slice(0, 2);
  if (normalized === 'ru') return 'ru';
  return 'en';
}

let currentLang: SupportedLang = 'en';

export function setLang(lang: SupportedLang): void {
  currentLang = lang;
}

export function getLang(): SupportedLang {
  return currentLang;
}

export function t(): LocaleShape {
  return LOCALES[currentLang];
}

export function getLocale(lang: SupportedLang): LocaleShape {
  return LOCALES[lang];
}
