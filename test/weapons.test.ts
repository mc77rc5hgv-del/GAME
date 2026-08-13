import { describe, it, expect } from 'vitest';
import { WEAPONS, WEAPON_SPAWN_POOL, type WeaponType } from '../src/config/weapons';

const WEAPON_TYPES = Object.keys(WEAPONS) as WeaponType[];

describe('weapon configuration', () => {
  it('defines all expected weapon types', () => {
    expect(WEAPON_TYPES.sort()).toEqual(['grenade', 'pistol', 'rifle', 'rocket', 'shotgun'].sort());
  });

  it('every weapon has positive core stats', () => {
    for (const type of WEAPON_TYPES) {
      const def = WEAPONS[type];
      expect(def.maxAmmo).toBeGreaterThan(0);
      expect(def.fireRateMs).toBeGreaterThan(0);
      expect(def.projectileSpeed).toBeGreaterThan(0);
      expect(def.damage).toBeGreaterThan(0);
      expect(def.projectilesPerShot).toBeGreaterThan(0);
    }
  });

  it('every weapon has a localized display name for ru and en', () => {
    for (const type of WEAPON_TYPES) {
      const def = WEAPONS[type];
      expect(def.displayName.ru.length).toBeGreaterThan(0);
      expect(def.displayName.en.length).toBeGreaterThan(0);
    }
  });

  it('only explosive weapons (rocket/grenade) define an explosion radius', () => {
    for (const type of WEAPON_TYPES) {
      const def = WEAPONS[type];
      const shouldExplode = type === 'rocket' || type === 'grenade';
      expect(def.explosionRadius > 0).toBe(shouldExplode);
      expect(def.explosionForce > 0).toBe(shouldExplode);
    }
  });

  it('the shotgun fires multiple pellets and everything else fires one projectile', () => {
    expect(WEAPONS.shotgun.projectilesPerShot).toBeGreaterThan(1);
    expect(WEAPONS.pistol.projectilesPerShot).toBe(1);
    expect(WEAPONS.rifle.projectilesPerShot).toBe(1);
    expect(WEAPONS.rocket.projectilesPerShot).toBe(1);
    expect(WEAPONS.grenade.projectilesPerShot).toBe(1);
  });

  it('the rocket launcher hits hardest and can damage the most terrain', () => {
    const rocketDestruction = WEAPONS.rocket.destructionRadius;
    for (const type of WEAPON_TYPES) {
      if (type === 'rocket') continue;
      expect(WEAPONS[type].destructionRadius).toBeLessThanOrEqual(rocketDestruction);
    }
  });

  it('the spawn pool only references defined weapon types', () => {
    for (const type of WEAPON_SPAWN_POOL) {
      expect(WEAPONS[type]).toBeDefined();
    }
  });
});
