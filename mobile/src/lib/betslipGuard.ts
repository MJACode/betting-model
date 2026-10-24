/**
 * The betslip add gate for a player who is not playing.
 *
 * Matt, 2026-10-24: "If a player is hurt and not playing you shouldn't be able
 * to add them to a bet." Both stores (useLineLegs, useParlaySlip) admit a new
 * leg through here, so a pill, a pick card, a player page and a restored slip
 * share one answer. The answer is the Stats board's own lookup: Out, IR, SUSP
 * and the IL are rejected; Questionable, Doubtful and Day-To-Day are not.
 * A game line and a custom leg have no player for that lookup, so they pass.
 */
import { playerIsSidelined, type InjuryIndex } from '@/lib/injuryStatus';
import { isGameSpec, lineLegKey, type LineLegSpec } from '@/lib/lineLegs';
import { playerNameFromPickLabel } from '@/lib/markets';
import { isPropModel } from '@/lib/modelMeta';

/** The player an add is about. `team` is omitted when the caller does not
 *  have one; the lookup then uses the name only when a single team lists it. */
export interface BetslipPlayer {
  sport: string;
  name: string | null | undefined;
  team?: string | null;
}

/**
 * The player on a model pick, or null when the pick is not a player prop.
 * The name is the token `playerNameFromPickLabel` already takes off the stored
 * label — the same token prop odds are keyed by. It is not a rebuilt line.
 */
export function betslipPlayerFromPick(
  pick: { sport: string; model_id: string; pick_label: string },
  team?: string | null,
): BetslipPlayer | null {
  if (!isPropModel(pick.model_id)) return null;
  const name = playerNameFromPickLabel(pick.pick_label);
  if (!name) return null;
  // A game total's label also matches the prop pattern ("SEA vs OAK Over 7.0").
  // That is not a player, and isPropModel already excludes game models; this
  // is the same guard the pick card uses so a stray label cannot block a team.
  if (/\s(?:vs|@)\s/.test(name)) return null;
  return { sport: pick.sport, name, team: team ?? null };
}

/**
 * The line-leg list after an add, or null when the add is a no-op.
 * Null covers "already in the slip" and "this player is sidelined".
 * A game spec has no player and is never rejected for an injury.
 */
export function lineLegsAfterAdd(
  specs: readonly LineLegSpec[],
  spec: LineLegSpec,
  index: InjuryIndex,
): LineLegSpec[] | null {
  const key = lineLegKey(spec);
  if (specs.some((s) => lineLegKey(s) === key)) return null;
  if (!isGameSpec(spec) && playerIsSidelined(index, spec.player_name, spec.team)) return null;
  return [...specs, spec];
}

/**
 * The pick-slip keys after an add, or null when the add is a no-op.
 * A null player is a game line (or a restore we cannot name): the injury
 * lookup has nothing to reject.
 */
export function slipKeysAfterAdd(
  keys: readonly string[],
  key: string,
  player: { name?: string | null; team?: string | null } | null | undefined,
  index: InjuryIndex,
): string[] | null {
  if (keys.includes(key)) return null;
  if (player && playerIsSidelined(index, player.name, player.team)) return null;
  return [...keys, key];
}
