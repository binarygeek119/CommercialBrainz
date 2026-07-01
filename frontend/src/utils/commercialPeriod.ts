/** Decade start years for commercial air-date estimates (e.g. 1990 → "1990s"). */
export const COMMERCIAL_DECADES = Array.from({ length: 9 }, (_, i) => 1940 + i * 10);

export function formatDecade(decade: number): string {
  return `${decade}s`;
}

export function formatCommercialPeriod(year?: number | null, decade?: number | null): string | null {
  if (year != null) {
    return decade != null && Math.floor(year / 10) * 10 !== decade
      ? `${year} (${formatDecade(decade)} estimate)`
      : String(year);
  }
  if (decade != null) return formatDecade(decade);
  return null;
}
