import { describe, it, expect } from 'vitest';
import { explosionFalloff, distance } from '../src/utils/physicsUtils';

describe('explosionFalloff', () => {
  it('is 1 at the epicenter', () => {
    expect(explosionFalloff(0, 100, 2)).toBe(1);
  });

  it('is 0 at or beyond the radius', () => {
    expect(explosionFalloff(100, 100, 2)).toBe(0);
    expect(explosionFalloff(150, 100, 2)).toBe(0);
  });

  it('is 0 for a non-positive radius', () => {
    expect(explosionFalloff(0, 0, 2)).toBe(0);
    expect(explosionFalloff(10, -5, 2)).toBe(0);
  });

  it('decreases monotonically as distance increases', () => {
    const near = explosionFalloff(10, 200, 2);
    const mid = explosionFalloff(100, 200, 2);
    const far = explosionFalloff(190, 200, 2);
    expect(near).toBeGreaterThan(mid);
    expect(mid).toBeGreaterThan(far);
    expect(far).toBeGreaterThan(0);
  });

  it('always stays within [0, 1] for in-range distances', () => {
    for (let d = 0; d <= 200; d += 10) {
      const falloff = explosionFalloff(d, 200, 2);
      expect(falloff).toBeGreaterThanOrEqual(0);
      expect(falloff).toBeLessThanOrEqual(1);
    }
  });

  it('a higher falloff power drops off faster at the same distance', () => {
    const gentle = explosionFalloff(100, 200, 1);
    const steep = explosionFalloff(100, 200, 3);
    expect(steep).toBeLessThan(gentle);
  });
});

describe('distance', () => {
  it('computes euclidean distance', () => {
    expect(distance(0, 0, 3, 4)).toBe(5);
    expect(distance(10, 10, 10, 10)).toBe(0);
  });
});
