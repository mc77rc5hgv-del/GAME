import { describe, it, expect, beforeEach } from 'vitest';
import { resolveSupportedLang, setLang, getLang, t, getLocale } from '../src/localization';
import { en } from '../src/localization/en';
import { ru } from '../src/localization/ru';

describe('resolveSupportedLang (platform requirement 2.14)', () => {
  it('maps the Yandex SDK "ru" language code to Russian', () => {
    expect(resolveSupportedLang('ru')).toBe('ru');
  });

  it('maps the Yandex SDK "en" language code to English', () => {
    expect(resolveSupportedLang('en')).toBe('en');
  });

  it('falls back to English for every unsupported SDK language code', () => {
    for (const code of ['tr', 'uk', 'kk', 'fr', 'de', 'zh', '']) {
      expect(resolveSupportedLang(code)).toBe('en');
    }
  });

  it('falls back to English for null/undefined (SDK unavailable)', () => {
    expect(resolveSupportedLang(null)).toBe('en');
    expect(resolveSupportedLang(undefined)).toBe('en');
  });

  it('is case-insensitive and tolerant of region suffixes (e.g. ru-RU)', () => {
    expect(resolveSupportedLang('RU')).toBe('ru');
    expect(resolveSupportedLang('ru-RU')).toBe('ru');
    expect(resolveSupportedLang('en-US')).toBe('en');
  });
});

describe('locale content', () => {
  beforeEach(() => setLang('en'));

  it('ru and en expose exactly the same set of keys', () => {
    expect(Object.keys(ru).sort()).toEqual(Object.keys(en).sort());
    for (const section of Object.keys(en) as (keyof typeof en)[]) {
      expect(Object.keys(ru[section]).sort()).toEqual(Object.keys(en[section]).sort());
    }
  });

  it('t() reflects the currently active language', () => {
    setLang('en');
    expect(getLang()).toBe('en');
    expect(t().menu.title).toBe(en.menu.title);

    setLang('ru');
    expect(getLang()).toBe('ru');
    expect(t().menu.title).toBe(ru.menu.title);
  });

  it('getLocale returns the requested locale regardless of the active one', () => {
    setLang('en');
    expect(getLocale('ru').menu.title).toBe(ru.menu.title);
  });
});
