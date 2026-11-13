"""Where the UFC study reads from. The study runs FROM its cache folder (every
script reads and writes its parquet files relative to the working directory);
these two paths are the inputs that live elsewhere."""
import os
import tempfile

STUDY = os.environ.get("UFC_STUDY_DIR", os.path.join(tempfile.gettempdir(), "ufc_research"))
MIRROR = os.environ.get("LOCAL_MIRROR_TABLES",
                        r"C:\Users\micha\Documents\betting_local_copies\supabase_mirror\tables")
CANON_DB = os.path.join(STUDY, "dl_canon", "canon.db")
UUD_CSV = os.path.join(STUDY, "dl_uud", "ufc-master.csv")
