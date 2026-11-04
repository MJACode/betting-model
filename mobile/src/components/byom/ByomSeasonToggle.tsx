import React from 'react';

import { ByomPillToggle } from '@/components/byom/ByomPillToggle';
import { useByomSeason } from '@/hooks/useByomSeason';
import type { ByomSeasonScope } from '@/lib/byomRecord';

const OPTIONS: { value: ByomSeasonScope; label: string }[] = [
  { value: 'all', label: 'All seasons' },
  { value: 'current', label: 'This season' },
];

export function ByomSeasonToggle() {
  const { scope, setScope } = useByomSeason();
  return <ByomPillToggle options={OPTIONS} value={scope} onChange={setScope} />;
}
