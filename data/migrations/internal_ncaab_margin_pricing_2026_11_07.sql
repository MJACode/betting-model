-- NCAAB winning-margin band pricing. INTERNAL ONLY.
--
-- Everything lives in schema `internal`, which is NOT in PostgREST's exposed
-- schemas. RLS is on for every table with NO policies; anon and authenticated
-- get no privilege on the schema, its tables, views, sequences or functions.
-- Nothing here writes to picks, picks_log, model_registry, push_sent,
-- social_post_queue or any table the app reads. The only write outside
-- `internal` is one row per function run in public.pipeline_log.
--
-- Bands, from the favourite's side (fav_margin = fav score - dog score):
--   fav_1_10  1 <= fav_margin <= 10      fav_11p  fav_margin >= 11
--   dog_1_10  -10 <= fav_margin <= -1    dog_11p  fav_margin <= -11
-- A college game cannot end tied, so the four bands sum to 1.
--
-- "Team wins by 11+" is the same outcome as that team at -10.5. For the
-- underdog that is DOG -10.5 (not dog +10.5, which is "dog loses by 10 or
-- fewer, or wins"), so the DK comparison column is dk_alt_dog_m10_5.

create schema if not exists internal;

revoke all on schema internal from public, anon, authenticated;
grant usage on schema internal to service_role;

alter default privileges in schema internal revoke all on tables    from public, anon, authenticated;
alter default privileges in schema internal revoke all on sequences from public, anon, authenticated;
alter default privileges in schema internal revoke all on functions from public, anon, authenticated;

-- ---------------------------------------------------------------- helpers
create or replace function internal.american_to_decimal(a numeric)
returns numeric language sql immutable as $$
  select case when a is null or a = 0 then null
              when a > 0 then 1 + a / 100.0
              else 1 + 100.0 / abs(a) end
$$;

create or replace function internal.prob_to_american(p numeric)
returns numeric language sql immutable as $$
  select case when p is null or p <= 0 or p >= 1 then null
              when p >= 0.5 then round(-100.0 * p / (1 - p))
              else round(100.0 * (1 - p) / p) end
$$;

-- Price at which a bet with win chance p returns +cushion EV per unit risked.
create or replace function internal.min_american(p numeric, cushion numeric default 0.03)
returns numeric language sql immutable as $$
  select case when p is null or p <= 0 or p >= 1 then null
              when (1 + cushion) / p >= 2 then ceil(((1 + cushion) / p - 1) * 100)
              else ceil(-100.0 / ((1 + cushion) / p - 1)) end
$$;

-- ---------------------------------------------------------------- 1. baseline
create table if not exists internal.ncaab_margin_baseline (
  abs_spread    numeric(4,1) not null,
  season_phase  text not null check (season_phase in ('nov','rest')),
  n_games       integer not null,
  mean_margin   numeric not null,   -- favourite's mean margin
  sd_margin     numeric not null,
  p_fav_1_10    numeric not null,
  p_fav_11p     numeric not null,
  p_dog_1_10    numeric not null,
  p_dog_11p     numeric not null,
  seasons_from  integer not null,
  seasons_to    integer not null,
  built_at      timestamptz not null default now(),
  primary key (abs_spread, season_phase)
);

-- Rebuild from ncaab_archive_lines. The archive stores many 2008-2021 games
-- twice (sbro + prediction_tracker, 44,175 game_ids); one row per game is
-- kept, prediction_tracker first. Pick'ems (close 0) have no favourite and
-- are left out. Window: every game whose |close| is within +/-1 of the grid
-- point. p_max_season lets the calibration check hold a season out.
create or replace function internal.refresh_ncaab_margin_baseline(p_max_season integer default null)
returns integer language plpgsql security invoker set search_path = '' as $$
declare
  t0 timestamptz := clock_timestamp();
  n  integer;
begin
  delete from internal.ncaab_margin_baseline;

  with base as (
    select distinct on (coalesce(l.game_id, l.game_date || l.home_name || l.away_name))
           l.season,
           case when substr(l.game_date, 6, 2) = '11' then 'nov' else 'rest' end as ph,
           abs(l.close_spread_home)::numeric as a,
           case when l.close_spread_home < 0 then l.home_score - l.away_score
                else l.away_score - l.home_score end as fm
      from public.ncaab_archive_lines l
     where l.close_spread_home is not null and l.close_spread_home <> 0
       and l.home_score is not null and l.away_score is not null
       and l.home_score <> l.away_score
       and (p_max_season is null or l.season <= p_max_season)
     order by coalesce(l.game_id, l.game_date || l.home_name || l.away_name),
              (l.source = 'prediction_tracker') desc
  ),
  grid as (
    select (g * 0.5)::numeric(4,1) as s, ph
      from generate_series(1, 70) g, (values ('nov'), ('rest')) v(ph)
  )
  insert into internal.ncaab_margin_baseline
    (abs_spread, season_phase, n_games, mean_margin, sd_margin,
     p_fav_1_10, p_fav_11p, p_dog_1_10, p_dog_11p, seasons_from, seasons_to)
  select g.s, g.ph, count(*),
         avg(b.fm), stddev_samp(b.fm),
         avg((b.fm between 1 and 10)::int),
         avg((b.fm >= 11)::int),
         avg((b.fm between -10 and -1)::int),
         avg((b.fm <= -11)::int),
         min(b.season), max(b.season)
    from grid g
    join base b on b.ph = g.ph and b.a between g.s - 1 and g.s + 1
   group by g.s, g.ph;

  get diagnostics n = row_count;

  insert into public.pipeline_log (run_date, step, status, records_in, records_out, duration_s, created_at)
  values (to_char(now() at time zone 'America/New_York', 'YYYY-MM-DD'),
          'internal:ncaab_margin_baseline', 'success', null, n,
          round(extract(epoch from clock_timestamp() - t0)::numeric, 2), now()::text);
  return n;
end $$;

-- ---------------------------------------------------------------- 2. prices
create table if not exists internal.ncaab_margin_prices (
  id                 bigint generated always as identity primary key,
  game_id            text not null,
  game_date          date not null,          -- ET
  commence_time      timestamptz not null,
  fav_team           text not null,
  dog_team           text not null,
  fav_is_home        boolean not null,
  neutral_site       boolean,
  center_spread      numeric(4,1) not null,  -- favourite's line, negative
  spread_source      text not null check (spread_source in ('pinnacle','median')),
  n_books            integer,
  season_phase       text not null,
  off_grid           boolean not null default false,  -- |spread| > 35: no fair prices
  fav_1_10_fair_prob numeric, fav_1_10_fair_american numeric, fav_1_10_min_odds numeric,
  fav_11p_fair_prob  numeric, fav_11p_fair_american  numeric, fav_11p_min_odds  numeric,
  dog_1_10_fair_prob numeric, dog_1_10_fair_american numeric, dog_1_10_min_odds numeric,
  dog_11p_fair_prob  numeric, dog_11p_fair_american  numeric, dog_11p_min_odds  numeric,
  dk_alt_fav_m10_5   numeric,   -- DK price, favourite -10.5  (= fav wins by 11+)
  dk_alt_dog_m10_5   numeric,   -- DK price, underdog  -10.5  (= dog wins by 11+)
  ev_fav_11p         numeric,
  ev_dog_11p         numeric,
  dk_ml_fav          numeric,
  dk_ml_dog          numeric,
  -- Reference only: vig-removed ML minus vig-removed alt -10.5. Biased by
  -- the alt ladder's uneven vig.
  dk_implied_fav_1_10 numeric,
  dk_implied_dog_1_10 numeric,
  computed_at        timestamptz not null,
  unique (game_id, computed_at)
);
create index if not exists ncaab_margin_prices_date_idx on internal.ncaab_margin_prices (game_date, game_id, computed_at desc);

-- Price every game on the ET date that has not tipped. Market centre:
-- Pinnacle's main spread, else the median main spread across books, rounded
-- to 0.5. Only pre-game quotes (snapshot_at <= commence_time, CLAUDE.md §6).
-- A new row is written only when an input changed since the game's last row,
-- so a 5-minute cadence keeps line-movement history without duplicates.
create or replace function internal.refresh_ncaab_margin_prices(p_date date default (now() at time zone 'America/New_York')::date)
returns integer language plpgsql security invoker set search_path = '' as $$
declare
  t0  timestamptz := clock_timestamp();
  now_ts timestamptz := now();
  n   integer;
begin
  with ev as (
    select e.game_id, e.commence_time::timestamptz as ct, e.neutral_site,
           e.home_espn_id, e.away_espn_id
      from public.ncaab_events e
     where (e.commence_time::timestamptz at time zone 'America/New_York')::date = p_date
       and e.commence_time::timestamptz > now_ts
  ),
  q as (  -- pre-game quotes for these games
    select o.game_id, o.bookmaker, o.market, o.spread_home, o.home_price, o.away_price
      from public.latest_odds o join ev on ev.game_id = o.game_id
     where o.market in ('spreads', 'alternate_spreads', 'h2h')
       and o.snapshot_at::timestamptz <= ev.ct
       and (o.market <> 'spreads' or o.spread_home between -60 and 60)  -- models/ncaab_quote_bounds.py range
  ),
  ctr as (
    select ev.*,
           pin.spread_home as pin_spread,
           med.med_spread, med.n_books
      from ev
      left join lateral (select spread_home from q where q.game_id = ev.game_id
                          and q.market = 'spreads' and q.bookmaker = 'pinnacle' limit 1) pin on true
      left join lateral (select percentile_cont(0.5) within group (order by spread_home) as med_spread,
                                count(*) as n_books
                           from q where q.game_id = ev.game_id and q.market = 'spreads') med on true
  ),
  c as (
    select ctr.*,
           case when pin_spread is not null then 'pinnacle' else 'median' end as src,
           round(coalesce(pin_spread, med_spread) * 2) / 2 as home_line
      from ctr
     where coalesce(pin_spread, med_spread) is not null
       and round(coalesce(pin_spread, med_spread) * 2) / 2 <> 0  -- pick'em: no favourite
  ),
  g as (
    select c.*,
           (c.home_line < 0) as fav_home,
           abs(c.home_line)::numeric(4,1) as abs_line,
           case when extract(month from (c.ct at time zone 'America/New_York')) = 11 then 'nov' else 'rest' end as ph
      from c
  ),
  dk as (
    select g.game_id,
      -- team at -10.5: home -> row spread_home = -10.5, home_price; away -> row +10.5, away_price
      (select case when g.fav_home then q.home_price else q.away_price end from q
        where q.game_id = g.game_id and q.bookmaker = 'draftkings' and q.market in ('alternate_spreads','spreads')
          and q.spread_home = case when g.fav_home then -10.5 else 10.5 end limit 1) as fav_m10_5,
      (select case when g.fav_home then q.away_price else q.home_price end from q
        where q.game_id = g.game_id and q.bookmaker = 'draftkings' and q.market in ('alternate_spreads','spreads')
          and q.spread_home = case when g.fav_home then -10.5 else 10.5 end limit 1) as dog_p10_5,
      (select case when g.fav_home then q.away_price else q.home_price end from q
        where q.game_id = g.game_id and q.bookmaker = 'draftkings' and q.market in ('alternate_spreads','spreads')
          and q.spread_home = case when g.fav_home then 10.5 else -10.5 end limit 1) as dog_m10_5,
      (select case when g.fav_home then q.home_price else q.away_price end from q
        where q.game_id = g.game_id and q.bookmaker = 'draftkings' and q.market in ('alternate_spreads','spreads')
          and q.spread_home = case when g.fav_home then 10.5 else -10.5 end limit 1) as fav_p10_5,
      (select case when g.fav_home then q.home_price else q.away_price end from q
        where q.game_id = g.game_id and q.bookmaker = 'draftkings' and q.market = 'h2h' limit 1) as ml_fav,
      (select case when g.fav_home then q.away_price else q.home_price end from q
        where q.game_id = g.game_id and q.bookmaker = 'draftkings' and q.market = 'h2h' limit 1) as ml_dog
    from g
  ),
  r as (
    select g.game_id, (g.ct at time zone 'America/New_York')::date as gd, g.ct,
           case when g.fav_home then th.display_name else ta.display_name end as fav_team,
           case when g.fav_home then ta.display_name else th.display_name end as dog_team,
           g.fav_home, g.neutral_site, -g.abs_line as center_spread, g.src, g.n_books, g.ph,
           (g.abs_line > 35) as off_grid,
           b.p_fav_1_10, b.p_fav_11p, b.p_dog_1_10, b.p_dog_11p,
           dk.fav_m10_5, dk.dog_m10_5, dk.ml_fav, dk.ml_dog,
           -- vig-removed pairs: fav -10.5 vs dog +10.5; dog -10.5 vs fav +10.5; ML
           (1/internal.american_to_decimal(dk.fav_m10_5)) /
             nullif(1/internal.american_to_decimal(dk.fav_m10_5) + 1/internal.american_to_decimal(dk.dog_p10_5), 0) as nv_fav_m10_5,
           (1/internal.american_to_decimal(dk.dog_m10_5)) /
             nullif(1/internal.american_to_decimal(dk.dog_m10_5) + 1/internal.american_to_decimal(dk.fav_p10_5), 0) as nv_dog_m10_5,
           (1/internal.american_to_decimal(dk.ml_fav)) /
             nullif(1/internal.american_to_decimal(dk.ml_fav) + 1/internal.american_to_decimal(dk.ml_dog), 0) as nv_ml_fav
      from g
      join dk on dk.game_id = g.game_id
      left join public.ncaab_teams th on th.espn_id = g.home_espn_id
      left join public.ncaab_teams ta on ta.espn_id = g.away_espn_id
      left join internal.ncaab_margin_baseline b
        on b.abs_spread = g.abs_line and b.season_phase = g.ph
  ),
  fin as (
    select r.*,
           r.p_fav_11p * internal.american_to_decimal(r.fav_m10_5) - 1 as ev_f,
           r.p_dog_11p * internal.american_to_decimal(r.dog_m10_5) - 1 as ev_d
      from r
  ),
  changed as (  -- skip when nothing moved since this game's last row
    select fin.* from fin
     where not exists (
       select 1 from (
         select p.* from internal.ncaab_margin_prices p
          where p.game_id = fin.game_id order by p.computed_at desc limit 1) last
        where last.center_spread = fin.center_spread
          and last.spread_source = fin.src
          and last.dk_alt_fav_m10_5 is not distinct from fin.fav_m10_5
          and last.dk_alt_dog_m10_5 is not distinct from fin.dog_m10_5
          and last.dk_ml_fav is not distinct from fin.ml_fav
          and last.dk_ml_dog is not distinct from fin.ml_dog
          and last.fav_11p_fair_prob is not distinct from fin.p_fav_11p)
  )
  insert into internal.ncaab_margin_prices (
    game_id, game_date, commence_time, fav_team, dog_team, fav_is_home, neutral_site,
    center_spread, spread_source, n_books, season_phase, off_grid,
    fav_1_10_fair_prob, fav_1_10_fair_american, fav_1_10_min_odds,
    fav_11p_fair_prob,  fav_11p_fair_american,  fav_11p_min_odds,
    dog_1_10_fair_prob, dog_1_10_fair_american, dog_1_10_min_odds,
    dog_11p_fair_prob,  dog_11p_fair_american,  dog_11p_min_odds,
    dk_alt_fav_m10_5, dk_alt_dog_m10_5, ev_fav_11p, ev_dog_11p,
    dk_ml_fav, dk_ml_dog, dk_implied_fav_1_10, dk_implied_dog_1_10, computed_at)
  select game_id, gd, ct, coalesce(fav_team, '?'), coalesce(dog_team, '?'), fav_home, neutral_site,
         center_spread, src, n_books, ph, off_grid,
         p_fav_1_10, internal.prob_to_american(p_fav_1_10), internal.min_american(p_fav_1_10),
         p_fav_11p,  internal.prob_to_american(p_fav_11p),  internal.min_american(p_fav_11p),
         p_dog_1_10, internal.prob_to_american(p_dog_1_10), internal.min_american(p_dog_1_10),
         p_dog_11p,  internal.prob_to_american(p_dog_11p),  internal.min_american(p_dog_11p),
         fav_m10_5, dog_m10_5, ev_f, ev_d,
         ml_fav, ml_dog,
         nv_ml_fav - nv_fav_m10_5,
         (1 - nv_ml_fav) - nv_dog_m10_5,
         now_ts
    from changed;

  get diagnostics n = row_count;

  insert into public.pipeline_log (run_date, step, status, records_in, records_out, duration_s, created_at)
  values (p_date::text, 'internal:ncaab_margin_prices', 'success', null, n,
          round(extract(epoch from clock_timestamp() - t0)::numeric, 2), now()::text);
  return n;
end $$;

-- ---------------------------------------------------------------- 3. manual DK odds
create table if not exists internal.ncaab_margin_dk_odds (
  id          bigint generated always as identity primary key,
  game_id     text not null,
  band        text not null check (band in ('fav_1_10','fav_11p','dog_1_10','dog_11p')),
  team        text not null,
  dk_american numeric not null check (dk_american <= -100 or dk_american >= 100),
  entered_at  timestamptz not null default now(),
  source      text not null default 'manual'
);
create index if not exists ncaab_margin_dk_odds_game_idx on internal.ncaab_margin_dk_odds (game_id, band, entered_at desc);

-- Latest price row per game x latest manual DK odds per (game, band).
-- team_mismatch: the entered team is not the band's team on the latest row
-- (the favourite flipped, or a typo). bet_flag is false when it mismatches.
create or replace view internal.ncaab_margin_edges as
with lp as (
  select distinct on (game_id) * from internal.ncaab_margin_prices order by game_id, computed_at desc
),
ld as (
  select distinct on (game_id, band) * from internal.ncaab_margin_dk_odds order by game_id, band, entered_at desc
),
bands as (
  select lp.game_id, lp.game_date, lp.commence_time, lp.computed_at, v.band, v.band_team, v.fair_prob, v.fair_american, v.min_odds
    from lp cross join lateral (values
      ('fav_1_10', lp.fav_team, lp.fav_1_10_fair_prob, lp.fav_1_10_fair_american, lp.fav_1_10_min_odds),
      ('fav_11p',  lp.fav_team, lp.fav_11p_fair_prob,  lp.fav_11p_fair_american,  lp.fav_11p_min_odds),
      ('dog_1_10', lp.dog_team, lp.dog_1_10_fair_prob, lp.dog_1_10_fair_american, lp.dog_1_10_min_odds),
      ('dog_11p',  lp.dog_team, lp.dog_11p_fair_prob,  lp.dog_11p_fair_american,  lp.dog_11p_min_odds)
    ) v(band, band_team, fair_prob, fair_american, min_odds)
)
select b.*, ld.team as dk_team, ld.dk_american, ld.entered_at, ld.source,
       (ld.team is not null and ld.team <> b.band_team) as team_mismatch,
       round((b.fair_prob * internal.american_to_decimal(ld.dk_american) - 1) * 100, 2) as edge_pct,
       coalesce(ld.team = b.band_team
                and internal.american_to_decimal(ld.dk_american) >= internal.american_to_decimal(b.min_odds), false) as bet_flag
  from bands b
  join ld on ld.game_id = b.game_id and ld.band = b.band;

-- ---------------------------------------------------------------- 4. results
create table if not exists internal.ncaab_margin_results (
  game_id     text primary key,
  game_date   date not null,
  home_score  integer not null,
  away_score  integer not null,
  fav_team    text not null,     -- favourite on the last pre-tip price row
  fav_margin  integer not null,
  band_hit    text not null check (band_hit in ('fav_1_10','fav_11p','dog_1_10','dog_11p')),
  settled_at  timestamptz not null default now()
);

-- Settle every final game on the ET date that has a pre-tip price row.
-- Score = sum of ncaab_period_scores (overtime included). Idempotent.
create or replace function internal.settle_ncaab_margin(p_date date default ((now() at time zone 'America/New_York')::date - 1))
returns integer language plpgsql security invoker set search_path = '' as $$
declare
  t0 timestamptz := clock_timestamp();
  n  integer;
begin
  with lp as (
    select distinct on (p.game_id) p.*
      from internal.ncaab_margin_prices p
     where p.game_date = p_date and p.computed_at < p.commence_time
     order by p.game_id, p.computed_at desc
  ),
  sc as (
    select ps.game_id, sum(ps.home_points)::int as hs, sum(ps.away_points)::int as aws
      from public.ncaab_period_scores ps join lp on lp.game_id = ps.game_id
     group by ps.game_id
  ),
  x as (
    select lp.game_id, lp.game_date, sc.hs, sc.aws, lp.fav_team,
           case when lp.fav_is_home then sc.hs - sc.aws else sc.aws - sc.hs end as fm
      from lp
      join sc on sc.game_id = lp.game_id
      join public.ncaab_events e on e.game_id = lp.game_id and e.status = 'STATUS_FINAL'
     where sc.hs <> sc.aws
  )
  insert into internal.ncaab_margin_results (game_id, game_date, home_score, away_score, fav_team, fav_margin, band_hit)
  select game_id, game_date, hs, aws, fav_team, fm,
         case when fm >= 11 then 'fav_11p' when fm >= 1 then 'fav_1_10'
              when fm >= -10 then 'dog_1_10' else 'dog_11p' end
    from x
  on conflict (game_id) do update
     set home_score = excluded.home_score, away_score = excluded.away_score,
         fav_margin = excluded.fav_margin, band_hit = excluded.band_hit, settled_at = now();

  get diagnostics n = row_count;

  insert into public.pipeline_log (run_date, step, status, records_in, records_out, duration_s, created_at)
  values (p_date::text, 'internal:ncaab_margin_settle', 'success', null, n,
          round(extract(epoch from clock_timestamp() - t0)::numeric, 2), now()::text);
  return n;
end $$;

-- One row per settled game x band, priced at the last pre-tip row.
-- Units: 1u to win, risk capped at 3u (tracking/discord_notifier.stake_for).
create or replace view internal.ncaab_margin_graded as
with lp as (
  select distinct on (p.game_id) p.*
    from internal.ncaab_margin_prices p
   where p.computed_at < p.commence_time
   order by p.game_id, p.computed_at desc
),
ld as (  -- manual DK odds entered before tip
  select distinct on (d.game_id, d.band) d.*
    from internal.ncaab_margin_dk_odds d join lp on lp.game_id = d.game_id
   where d.entered_at < lp.commence_time
   order by d.game_id, d.band, d.entered_at desc
),
b as (
  select r.game_id, r.game_date, lp.center_spread, lp.season_phase, r.fav_margin, r.band_hit,
         v.band, v.fair_prob, v.min_odds, v.alt_price, (r.band_hit = v.band) as hit
    from internal.ncaab_margin_results r
    join lp on lp.game_id = r.game_id
    cross join lateral (values
      ('fav_1_10', lp.fav_1_10_fair_prob, lp.fav_1_10_min_odds, null::numeric),
      ('fav_11p',  lp.fav_11p_fair_prob,  lp.fav_11p_min_odds,  lp.dk_alt_fav_m10_5),
      ('dog_1_10', lp.dog_1_10_fair_prob, lp.dog_1_10_min_odds, null::numeric),
      ('dog_11p',  lp.dog_11p_fair_prob,  lp.dog_11p_min_odds,  lp.dk_alt_dog_m10_5)
    ) v(band, fair_prob, min_odds, alt_price)
)
select b.*, (b.fair_prob - b.hit::int)^2 as brier,
       ld.dk_american,
       internal.american_to_decimal(ld.dk_american) >= internal.american_to_decimal(b.min_odds) as bet_flag,
       case when ld.dk_american is null then null
            when b.hit then least(1.0, 3.0 * (internal.american_to_decimal(ld.dk_american) - 1))
            else -least(3.0, 1.0 / (internal.american_to_decimal(ld.dk_american) - 1)) end as units_manual,
       case when b.alt_price is null then null
            when b.hit then least(1.0, 3.0 * (internal.american_to_decimal(b.alt_price) - 1))
            else -least(3.0, 1.0 / (internal.american_to_decimal(b.alt_price) - 1)) end as units_alt
  from b
  left join ld on ld.game_id = b.game_id and ld.band = b.band;

-- ---------------------------------------------------------------- 6. today
create or replace view internal.ncaab_margin_today as
with lp as (
  select distinct on (p.game_id) p.*
    from internal.ncaab_margin_prices p
   where p.game_date = (now() at time zone 'America/New_York')::date
   order by p.game_id, p.computed_at desc
)
select lp.commence_time, lp.dog_team || ' vs ' || lp.fav_team as matchup,
       lp.fav_team || ' ' || lp.center_spread as spread, lp.spread_source,
       v.band, v.team, v.fair_american, v.min_odds, v.alt_price as dk_alt_m10_5, v.alt_ev as ev_11p,
       e.dk_american as dk_manual, e.edge_pct, e.bet_flag, e.team_mismatch, lp.computed_at
  from lp
  cross join lateral (values
    (1, 'fav_1_10', lp.fav_team, lp.fav_1_10_fair_american, lp.fav_1_10_min_odds, null::numeric, null::numeric),
    (2, 'fav_11p',  lp.fav_team, lp.fav_11p_fair_american,  lp.fav_11p_min_odds,  lp.dk_alt_fav_m10_5, lp.ev_fav_11p),
    (3, 'dog_1_10', lp.dog_team, lp.dog_1_10_fair_american, lp.dog_1_10_min_odds, null::numeric, null::numeric),
    (4, 'dog_11p',  lp.dog_team, lp.dog_11p_fair_american,  lp.dog_11p_min_odds,  lp.dk_alt_dog_m10_5, lp.ev_dog_11p)
  ) v(ord, band, team, fair_american, min_odds, alt_price, alt_ev)
  left join internal.ncaab_margin_edges e on e.game_id = lp.game_id and e.band = v.band
 order by lp.commence_time, lp.game_id, v.ord;

-- ---------------------------------------------------------------- lock down
alter table internal.ncaab_margin_baseline enable row level security;
alter table internal.ncaab_margin_prices   enable row level security;
alter table internal.ncaab_margin_dk_odds  enable row level security;
alter table internal.ncaab_margin_results  enable row level security;
-- No policies, on purpose. postgres bypasses RLS as owner; service_role has BYPASSRLS.

revoke all on all tables    in schema internal from public, anon, authenticated;
revoke all on all sequences in schema internal from public, anon, authenticated;
revoke all on all functions in schema internal from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema internal to service_role;
grant usage, select on all sequences in schema internal to service_role;
grant execute on all functions in schema internal to service_role;

-- Views run as their owner (postgres) by default, which would let anyone with
-- SELECT on a view read past RLS. Nobody but service_role has SELECT, but run
-- them as the caller anyway so the guard does not hang on one grant.
alter view internal.ncaab_margin_edges  set (security_invoker = true);
alter view internal.ncaab_margin_graded set (security_invoker = true);
alter view internal.ncaab_margin_today  set (security_invoker = true);
