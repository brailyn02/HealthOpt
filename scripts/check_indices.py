import sqlite3
DB = "D:/23AIBox-DFinder/chembl_36_sqlite/chembl_36/chembl_36_sqlite/chembl_36.db"
conn = sqlite3.connect(DB)
idxs = conn.execute(
    "SELECT tbl_name, name FROM sqlite_master "
    "WHERE type='index' AND tbl_name IN ('activities','assays') "
    "ORDER BY tbl_name, name"
).fetchall()
print(f"Indices on activities/assays: {len(idxs)}")
for t, n in idxs:
    print(f"  {t:12s} {n}")
conn.close()
