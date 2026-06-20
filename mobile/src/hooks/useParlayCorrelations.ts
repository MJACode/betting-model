/**
 * Correlation table for the parlay copula engine.
 *
 * Phase 1: returns the bundled `PARLAY_CORRELATION_PRIORS` (no network). This is
 * the stable seam Phase 2 will extend — once the `parlay_correlations` Supabase
 * table + estimator land, this hook will fetch `source='empirical'` rows and
 * overlay them on the priors, with the priors as the offline fallback so the
 * feature never hard-depends on the network.
 */

import { PARLAY_CORRELATION_PRIORS, type RhoTable } from '@/lib/parlayCorrelation';

export function useParlayCorrelations(): RhoTable {
  // Phase 2 TODO: fetch parlay_correlations and overlay empirical ρ here.
  return PARLAY_CORRELATION_PRIORS;
}
