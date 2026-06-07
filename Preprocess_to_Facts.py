import os
import glob
import pandas as pd

base_folder = "/Users/keita/Desktop/DS_Top_M_Streamlit/All_Data"
out_folder  = base_folder  # 出力も All_Data 直下に置くのがおすすめ
os.makedirs(out_folder, exist_ok=True)

LEVELS = ["S4_Gouhan_CSV", "S5_Gouhan_CSV", "S6_Gouhan_CSV"]

def parse_meta_from_filename(path: str):
    name = os.path.basename(path).replace(".csv", "")
    parts = name.split("-")
    nendo = int(parts[0])
    kai = int(parts[2])   # 例: 2024-6-3-... の "3"
    return nendo, kai

def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")

# =========================
# 1) 平均点 facts を作る
# =========================
fact_rows = []

for level in LEVELS:
    level_dir = os.path.join(base_folder, level)
    pattern = os.path.join(level_dir, "*_with_examinees.csv")
    paths = sorted(glob.glob(pattern))

    for p in paths:
        nendo, kai = parse_meta_from_filename(p)
        df = pd.read_csv(p)

        keep = [c for c in ["科目", "配点", "平均点", "受験者数_全体"] if c in df.columns]
        if not keep:
            continue
        df = df[keep].copy()

        df["年度"] = nendo
        df["回"] = kai

        for col in ["配点", "平均点", "受験者数_全体", "年度", "回"]:
            if col in df.columns:
                df[col] = to_num(df[col])

        df = df.dropna(subset=["科目"])
        df["科目"] = df["科目"].astype(str).str.strip()
        df = df[df["科目"] != ""]
        df = df.dropna(subset=["配点", "平均点"], how="all")

        # どのレベル由来か残したいなら（任意）
        # df["レベル"] = level.replace("_Gouhan_CSV","")
        grade = int(level[1])
        df["学年"] = grade
        df["レベル"] = f"S{grade}"

        fact_rows.append(df)

facts = pd.concat(fact_rows, ignore_index=True) if fact_rows else pd.DataFrame(
    columns=["学年","レベル","年度","回","科目","配点","平均点","受験者数_全体"]
)

# 受験者数の列名を統一
if "受験者数_全体" in facts.columns:
    facts = facts.rename(columns={"受験者数_全体": "受験者数"})
elif "受験者数" not in facts.columns:
    facts["受験者数"] = pd.NA

# 便利列
facts["順序"] = (facts["年度"].fillna(0).astype(int) * 100 + facts["回"].fillna(0).astype(int))
facts["表示軸"] = (
    facts["年度"].fillna(0).astype(int).astype(str)
    + "年 第"
    + facts["回"].fillna(0).astype(int).astype(str)
    + "回"
)

# 科目順（任意）
subject_order = {
    "国語": 1, "算数": 2, "理科": 3, "社会": 4,
    "2科目": 5, "3科目": 6, "4科目": 7,
    "理社": 8, "算理": 9, "国社": 10
}
facts["科目順"] = facts["科目"].map(subject_order).fillna(999).astype(int)

# ソート（学年列がある前提）
facts = facts.sort_values(["学年", "順序", "科目順"], kind="stable").reset_index(drop=True)
facts = facts.drop(columns=["科目順"])

# 列順を整理（学年/レベルを残す！）
facts = facts[["学年","レベル","年度","回","順序","表示軸","科目","配点","平均点","受験者数"]]

# 最後に保存
facts_out = os.path.join(out_folder, "facts.csv")
facts.to_csv(facts_out, index=False)
print("saved:", facts_out, "rows=", len(facts))



# =========================
# 2) 偏差値 hensachi_facts を作る
# =========================
hens_rows = []

for level in LEVELS:
    level_dir = os.path.join(base_folder, level)
    pattern = os.path.join(level_dir, "*_hensachi.csv")
    paths = sorted(glob.glob(pattern))

    for p in paths:
        nendo, kai = parse_meta_from_filename(p)
        df = pd.read_csv(p)

        keep = [c for c in ["科目", "偏差値", "得点"] if c in df.columns]
        if not keep:
            continue
        df = df[keep].copy()

        df["年度"] = nendo
        df["回"] = kai

        for col in ["偏差値", "得点", "年度", "回"]:
            if col in df.columns:
                df[col] = to_num(df[col])

        df = df.dropna(subset=["科目"])
        df["科目"] = df["科目"].astype(str).str.strip()
        df = df[df["科目"] != ""]
        df = df.dropna(subset=["偏差値", "得点"], how="any")

        # df["レベル"] = level.replace("_Gouhan_CSV","")  # 任意
        grade = int(level[1])
        df["学年"] = grade
        df["レベル"] = f"S{grade}"
        
        hens_rows.append(df)

hensachi_facts = pd.concat(hens_rows, ignore_index=True) if hens_rows else pd.DataFrame(
    columns=["学年","レベル","年度","回","科目","偏差値","得点"]
)

# 重複除去（学年・レベルも含めるのが安全）
hensachi_facts = hensachi_facts.drop_duplicates(
    subset=["学年","年度","回","科目","偏差値","得点"]
)

# 並びを固定（Streamlitで扱いやすく）
hensachi_facts = hensachi_facts.sort_values(
    ["学年","年度","回","科目","偏差値"],
    kind="stable"
).reset_index(drop=True)

# 列順を揃える
hensachi_facts = hensachi_facts[
    ["学年","レベル","年度","回","科目","偏差値","得点"]
]

# 保存
hens_out = os.path.join(out_folder, "hensachi_facts.csv")
hensachi_facts.to_csv(hens_out, index=False)
print("saved:", hens_out, "rows=", len(hensachi_facts))

