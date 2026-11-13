"""Copy the UFC research tables out of the local mirror into one folder."""
import glob
import pyarrow.dataset as ds
import pyarrow.compute as pc

from _paths import MIRROR as M, STUDY as OUT


def load(t, flt=None):
    d = ds.dataset(glob.glob(f"{M}\\{t}\\*.parquet"), format="parquet")
    return d.to_table(filter=flt).to_pandas()


g = load("public.games", pc.field("sport") == "UFC")
g.to_parquet(f"{OUT}\\games.parquet"); print("games", len(g))
fl = load("public.ufc_fight_log"); fl.to_parquet(f"{OUT}\\fight_log.parquet"); print("fight_log", len(fl))
f = load("public.fighters"); f.to_parquet(f"{OUT}\\fighters.parquet"); print("fighters", len(f))
p = load("public.picks", pc.field("sport") == "UFC"); p.to_parquet(f"{OUT}\\picks.parquet"); print("picks", len(p))
