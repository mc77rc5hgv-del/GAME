export type WeaponType = 'pistol' | 'shotgun' | 'rifle' | 'rocket' | 'grenade';

export interface WeaponDefinition {
  type: WeaponType;
  displayName: { ru: string; en: string };
  maxAmmo: number;
  fireRateMs: number;
  projectileSpeed: number;
  damage: number;
  knockback: number;
  recoil: number;
  spreadDeg: number;
  projectilesPerShot: number;
  explosionRadius: number;
  explosionForce: number;
  destructionRadius: number;
  projectileGravityScale: number;
  color: number;
  muzzleOffset: { x: number; y: number };
  size: { width: number; height: number };
}

export const WEAPONS: Record<WeaponType, WeaponDefinition> = {
  pistol: {
    type: 'pistol',
    displayName: { ru: 'Пистолет', en: 'Pistol' },
    maxAmmo: 12,
    fireRateMs: 260,
    projectileSpeed: 22,
    damage: 8,
    knockback: 6,
    recoil: 5,
    spreadDeg: 2,
    projectilesPerShot: 1,
    explosionRadius: 0,
    explosionForce: 0,
    destructionRadius: 0,
    projectileGravityScale: 0,
    color: 0xd7d7d7,
    muzzleOffset: { x: 34, y: -4 },
    size: { width: 26, height: 12 },
  },
  shotgun: {
    type: 'shotgun',
    displayName: { ru: 'Дробовик', en: 'Shotgun' },
    maxAmmo: 6,
    fireRateMs: 680,
    projectileSpeed: 19,
    damage: 6,
    knockback: 5,
    recoil: 24,
    spreadDeg: 16,
    projectilesPerShot: 7,
    explosionRadius: 0,
    explosionForce: 0,
    destructionRadius: 0,
    projectileGravityScale: 0.15,
    color: 0xc98a3a,
    muzzleOffset: { x: 32, y: -4 },
    size: { width: 32, height: 14 },
  },
  rifle: {
    type: 'rifle',
    displayName: { ru: 'Автомат', en: 'Assault Rifle' },
    maxAmmo: 30,
    fireRateMs: 105,
    projectileSpeed: 26,
    damage: 5,
    knockback: 3,
    recoil: 4,
    spreadDeg: 3.5,
    projectilesPerShot: 1,
    explosionRadius: 0,
    explosionForce: 0,
    destructionRadius: 0,
    projectileGravityScale: 0,
    color: 0x5aa9e6,
    muzzleOffset: { x: 38, y: -4 },
    size: { width: 38, height: 12 },
  },
  rocket: {
    type: 'rocket',
    displayName: { ru: 'Гранатомёт', en: 'Rocket Launcher' },
    maxAmmo: 3,
    fireRateMs: 900,
    projectileSpeed: 13,
    damage: 22,
    knockback: 22,
    recoil: 42,
    spreadDeg: 0,
    projectilesPerShot: 1,
    explosionRadius: 190,
    explosionForce: 95,
    destructionRadius: 120,
    projectileGravityScale: 0.35,
    color: 0xe6473a,
    muzzleOffset: { x: 34, y: -2 },
    size: { width: 40, height: 18 },
  },
  grenade: {
    type: 'grenade',
    displayName: { ru: 'Гранатомёт-Мортира', en: 'Grenade Launcher' },
    maxAmmo: 4,
    fireRateMs: 560,
    projectileSpeed: 15,
    damage: 16,
    knockback: 17,
    recoil: 26,
    spreadDeg: 1.5,
    projectilesPerShot: 1,
    explosionRadius: 140,
    explosionForce: 72,
    destructionRadius: 90,
    projectileGravityScale: 0.85,
    color: 0x6dbf5a,
    muzzleOffset: { x: 30, y: -4 },
    size: { width: 30, height: 16 },
  },
};

export const WEAPON_SPAWN_POOL: WeaponType[] = ['pistol', 'shotgun', 'rifle', 'rocket', 'grenade'];
