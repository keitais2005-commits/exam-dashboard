import os
import re
import tabula
import pandas as pd

DEBUG_PRINT_COLUMNS = True  # columns を出すか
HENSACHI_SCAN_START = 6     # 偏差値表らへんが始まりがちなindex（軽量化）
HENSACHI_SCAN_END = 20      # 走査上限（pdfによって増減してもOK）

# ==========================
# 偏差値換算表 抽出
# ==========================
def extract_hensachi_from_table(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=["科目", "偏差値", "得点"])

    df = raw_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # ---- パターンA：列名に偏差値が並んでいる
    numeric_cols = []
    for c in df.columns:
        s = str(c).strip()
        if re.fullmatch(r"\d{2}", s) or re.fullmatch(r"\d{2}\.\d+", s):
            numeric_cols.append(c)

    if numeric_cols:
        subj_col = df.columns[0]
        long_df = df[[subj_col] + numeric_cols].copy()
        long_df = long_df.rename(columns={subj_col: "科目"})
        long_df["科目"] = long_df["科目"].replace("", pd.NA).ffill()

        melted = long_df.melt(id_vars=["科目"], var_name="偏差値", value_name="得点")
        melted["偏差値"] = pd.to_numeric(melted["偏差値"], errors="coerce")
        melted["得点"] = pd.to_numeric(melted["得点"].astype(str).str.replace(",", ""), errors="coerce")
        melted = melted.dropna(subset=["科目", "偏差値", "得点"])
        return melted[["科目", "偏差値", "得点"]]

    # ---- パターンB：偏差値が行として残っている
    df2 = df.dropna(how="all")
    if df2.empty:
        return pd.DataFrame(columns=["科目", "偏差値", "得点"])

    head = df2.head(5).copy()
    target_row_idx = None
    for i in head.index:
        row = head.loc[i].astype(str).str.strip().tolist()
        cnt = sum(bool(re.fullmatch(r"\d{2}", x)) for x in row)
        if cnt >= 3:
            target_row_idx = i
            break

    if target_row_idx is None:
        return pd.DataFrame(columns=["科目", "偏差値", "得点"])

    hensachi_row = df2.loc[target_row_idx].astype(str).str.strip().tolist()
    df_body = df2.drop(index=target_row_idx).copy()
    df_body.columns = hensachi_row

    subj_col = df_body.columns[0]
    cols = [c for c in df_body.columns if re.fullmatch(r"\d{2}", str(c).strip())]
    if not cols:
        return pd.DataFrame(columns=["科目", "偏差値", "得点"])

    df_body = df_body[[subj_col] + cols].copy()
    df_body = df_body.rename(columns={subj_col: "科目"})
    df_body["科目"] = df_body["科目"].replace("", pd.NA).ffill()

    melted = df_body.melt(id_vars=["科目"], var_name="偏差値", value_name="得点")
    melted["偏差値"] = pd.to_numeric(melted["偏差値"], errors="coerce")
    melted["得点"] = pd.to_numeric(melted["得点"].astype(str).str.replace(",", ""), errors="coerce")
    melted = melted.dropna(subset=["科目", "偏差値", "得点"])
    return melted[["科目", "偏差値", "得点"]]


# ==========================
# 便利関数（列名ゆれ対策）
# ==========================
def _norm_str(x) -> str:
    return "" if x is None else str(x).strip()

def find_col_contains(df: pd.DataFrame, keywords, prefer_first=True):
    if df is None or df.empty:
        return None
    hits = []
    for c in df.columns:
        s = _norm_str(c)
        for k in keywords:
            if k in s:
                hits.append(c)
                break
    if not hits:
        return None
    return hits[0] if prefer_first else hits[-1]

def choose_total_numeric_col(df: pd.DataFrame, rows_mask=None):
    if df is None or df.empty:
        return None
    work = df.loc[rows_mask].copy() if rows_mask is not None else df.copy()
    if work.empty:
        return None

    best_col, best_cnt = None, -1
    for c in work.columns:
        s = work[c].astype(str).str.replace(",", "").str.strip()
        nums = pd.to_numeric(s, errors="coerce")
        cnt = nums.notna().sum()
        if cnt > best_cnt:
            best_cnt, best_col = cnt, c
    return best_col

def safe_to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "").str.strip(), errors="coerce")


# ==========================
# メイン：S4/S5/S6 を全部回す
# ==========================
base_folder = "/Users/keita/Desktop/DS_Top_M_Streamlit/All_Data"

for level in ["S4_Gouhan_PDF", "S5_Gouhan_PDF", "S6_Gouhan_PDF"]:
    input_folder = os.path.join(base_folder, level)
    output_folder = os.path.join(base_folder, level.replace("_PDF", "_CSV"))
    os.makedirs(output_folder, exist_ok=True)

    print(f"📂 処理中フォルダ: {input_folder}")
    print(f"📁 出力フォルダ: {output_folder}")

    for file in sorted(os.listdir(input_folder)):
        if not file.endswith(".pdf"):
            continue

        input_path = os.path.join(input_folder, file)
        print(f"📄 {level} / {file} を処理中...")

        dfs = tabula.read_pdf(
            input_path,
            pages="all",
            lattice=True,
            multiple_tables=True
        )

        if len(dfs) < 6:
            print("⚠ テーブルが6個未満です。スキップします。")
            continue

        # ① score / examinee
        score_df = dfs[4]
        examinee_df = dfs[5]

        if score_df is None or score_df.empty or examinee_df is None or examinee_df.empty:
            print("⚠ score_df / examinee_df が空です。スキップします。")
            continue

        if DEBUG_PRINT_COLUMNS:
            print("✅ score_df columns:", list(score_df.columns))
            print("✅ examinee_df columns:", list(examinee_df.columns))

        # ===== 受験者数 =====
        df_ex = examinee_df.copy()
        group_col = find_col_contains(df_ex, ["科目数"]) or df_ex.columns[0]
        gender_col = find_col_contains(df_ex, ["全体", "区分", "性別"]) or (df_ex.columns[1] if len(df_ex.columns) >= 2 else df_ex.columns[0])

        df_ex[group_col] = df_ex[group_col].replace("", pd.NA).ffill()

        gender_vals = df_ex[gender_col].astype(str).str.strip()
        male_rows = gender_vals.eq("男")
        if male_rows.sum() == 0:
            alt_rows = gender_vals.str.contains("計|合計|総数", regex=True, na=False)
            rows_mask = alt_rows if alt_rows.sum() > 0 else None
        else:
            rows_mask = male_rows

        total_col = choose_total_numeric_col(df_ex, rows_mask=rows_mask)
        if total_col is None:
            print("⚠ 受験者数の数値列を特定できませんでした。受験者数は空で出力します。")
            total_map_by_points = {}
        else:
            totals = df_ex.copy()
            if rows_mask is not None:
                totals = totals.loc[rows_mask].copy()

            totals = totals[[group_col, total_col]].copy()
            totals = totals.rename(columns={group_col: "科目数", total_col: "受験者数_全体"})
            totals["受験者数_全体"] = safe_to_numeric(totals["受験者数_全体"])

            subject_points = {"2科目": 300, "3科目": 400, "4科目": 500}
            totals["科目数"] = totals["科目数"].astype(str).str.strip()
            totals["配点"] = totals["科目数"].map(subject_points)
            totals = totals.dropna(subset=["配点", "受験者数_全体"])

            total_map_by_points = dict(zip(totals["配点"].astype(int), totals["受験者数_全体"].astype(int)))
            print("👥 受験者数マップ（配点ベース）:", total_map_by_points)

        # ===== score_df 整形 =====
        score_df = score_df.copy()
        score_df.columns = [str(c).strip() for c in score_df.columns]

        if "科目" not in score_df.columns:
            score_df = score_df.rename(columns={score_df.columns[0]: "科目"})
        if "配点" not in score_df.columns and len(score_df.columns) >= 2:
            score_df = score_df.rename(columns={score_df.columns[1]: "配点"})

        avg_col = find_col_contains(score_df, ["平均点", "平均"])
        if avg_col and avg_col != "平均点":
            score_df = score_df.rename(columns={avg_col: "平均点"})
            avg_col = "平均点"

        if "配点" in score_df.columns:
            score_df["配点"] = safe_to_numeric(score_df["配点"])
        if avg_col and avg_col in score_df.columns:
            score_df[avg_col] = safe_to_numeric(score_df[avg_col])

        score_df["受験者数_全体"] = score_df.get("配点", pd.Series([pd.NA]*len(score_df))).map(total_map_by_points)

        if "科目" in score_df.columns and "配点" in score_df.columns:
            score_df["科目"] = score_df["科目"].fillna("").astype(str).str.strip()
            score_df.loc[(score_df["科目"] == "") & (score_df["配点"] == 300), "科目"] = "2科目"
            score_df.loc[(score_df["科目"] == "") & (score_df["配点"] == 400), "科目"] = "3科目"
            score_df.loc[(score_df["科目"] == "") & (score_df["配点"] == 500), "科目"] = "4科目"

        output_path = os.path.join(output_folder, file.replace(".pdf", "_with_examinees.csv"))
        score_df.to_csv(output_path, index=False)
        print(f"　→ {output_path} を出力しました")

        # ② 偏差値換算表
        hensachi_dfs = []
        start_i = min(HENSACHI_SCAN_START, len(dfs))
        end_i = min(HENSACHI_SCAN_END, len(dfs))

        for idx in range(start_i, end_i):
            t = dfs[idx]
            if t is None or t.empty:
                continue
            h = extract_hensachi_from_table(t)
            if not h.empty:
                hensachi_dfs.append(h)

        if not hensachi_dfs:
            for idx in range(len(dfs)):
                if idx in [4, 5]:
                    continue
                t = dfs[idx]
                if t is None or t.empty:
                    continue
                h = extract_hensachi_from_table(t)
                if not h.empty:
                    hensachi_dfs.append(h)

        if hensachi_dfs:
            hensachi_all = pd.concat(hensachi_dfs, ignore_index=True)
            hensachi_out_path = os.path.join(output_folder, file.replace(".pdf", "_hensachi.csv"))
            hensachi_all.to_csv(hensachi_out_path, index=False)
            print(f"　→ 偏差値換算表を {hensachi_out_path} に出力しました")
        else:
            print("⚠ このPDFからは偏差値換算表を抽出できませんでした")
