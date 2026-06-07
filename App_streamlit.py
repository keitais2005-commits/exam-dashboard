import os
import pandas as pd
import streamlit as st
import altair as alt
import numpy as np

DATA_DIR = "/Users/keita/Desktop/DS_Top_M_Streamlit/All_Data"
FACTS_DEFAULT = os.path.join(DATA_DIR, "facts.csv")
HENSACHI_DEFAULT = os.path.join(DATA_DIR, "hensachi_facts.csv")


st.set_page_config(page_title="中学模試ダッシュボード", layout="wide")

# =========================
# Loaders（キャッシュ推奨）
# =========================
@st.cache_data
def load_facts(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    for col in ["年度", "回", "配点", "平均点", "受験者数"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["順序"] = df["年度"] * 100 + df["回"]
    df["表示軸"] = (
        df["年度"].astype(int).astype(str)
        + "年 第"
        + df["回"].astype(int).astype(str)
        + "回"
    )
    return df

@st.cache_data
def load_hensachi(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["偏差値", "得点", "年度", "回"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def score_to_hensachi(df: pd.DataFrame, score: float, subject: str) -> float:
    tmp = df[df["科目"] == subject][["得点", "偏差値"]].dropna().copy()
    tmp = tmp.sort_values("得点")
    x = tmp["得点"].to_numpy()
    y = tmp["偏差値"].to_numpy()

    # 範囲外は端に寄せる（外挿しない）
    score_clipped = np.clip(score, x.min(), x.max())
    return float(np.interp(score_clipped, x, y))


# =========================
# 画面切り替え
# =========================
view_mode = st.sidebar.radio(
    "表示モード",
    ["科目別平均点", "偏差値換算表"],
    index=0
)

# ======================================================
# 科目別平均点ビュー
# ======================================================
if view_mode == "科目別平均点":
    st.title("模試ダッシュボード | 科目別平均点一覧")

    # パスは固定
    facts_path = FACTS_DEFAULT
    if not os.path.exists(facts_path):
        st.error("facts.csv が見つかりません。管理者に連絡してください。")
        st.stop()

    df = load_facts(facts_path)

    # =========================
    # サイドバー：条件選択（全部ここ）
    # =========================
    with st.sidebar:
        st.header("条件選択")

        # 学年
        if "学年" in df.columns:
            grades = sorted(df["学年"].dropna().unique().tolist())
            sel_grades = st.multiselect("学年", grades, default=grades)
            df = df[df["学年"].isin(sel_grades)]
        else:
            st.info("学年列がないため学年フィルタは表示しません")

        years = sorted(df["年度"].dropna().unique().tolist())
        exams = sorted(df["回"].dropna().unique().tolist())
        subjects = sorted(df["科目"].dropna().unique().tolist())

        sel_years = st.multiselect("年度", years, default=years)
        sel_exams = st.multiselect("回", exams, default=exams)
        sel_subjs = st.multiselect(
            "科目（1つ推奨）",
            subjects,
            default=[subjects[0]] if subjects else []
        )

        metric = st.radio("グラフに使う指標", ["平均点", "受験者数"], index=0)

        fix_y_to_points = False
        if metric == "平均点":
            fix_y_to_points = st.checkbox("Y軸を配点に固定する", value=True)

        st.divider()
        st.subheader("自分の点数（合計）")

        all_subjects = sorted(df["科目"].dropna().unique().tolist())
        picked = st.multiselect("受けた科目を選択", all_subjects, default=["国語", "算数"])

        user_scores = {}
        for s in picked:
            user_scores[s] = st.number_input(
                f"{s} の得点", min_value=0, step=1, value=0, key=f"score_{s}"
            )

        user_total = int(sum(user_scores.values()))
        st.metric("あなたの合計点", user_total)

    # =========================
    # フィルタ適用（結果用）
    # =========================
    view = df[
        df["年度"].isin(sel_years)
        & df["回"].isin(sel_exams)
        & df["科目"].isin(sel_subjs)
    ].copy()

    # =========================
    # メイン：結果はタブで切替
    # =========================
    tab_table, tab_sum, tab_chart = st.tabs(
    ["① 平均点表", "② 合計：平均推移 vs 自分", f"③ {('平均点' if metric=='平均点' else '受験者数')}グラフ"]
    )


    # -------- ① 平均点表 --------
    with tab_table:
        st.subheader("平均点表")
        st.dataframe(
            view.sort_values(["順序", "科目"]).reset_index(drop=True),
            use_container_width=True
        )

    # -------- ② 合計：平均推移 vs 自分 --------
    with tab_sum:
        st.subheader("科目セット合計：平均推移 vs 自分")

        if len(picked) == 0:
            st.info("サイドバーで科目を1つ以上選んでね")
        else:
            sum_avg = (
                df[df["科目"].isin(picked)]
                .groupby(["年度", "回"], as_index=False)["平均点"].sum()
                .rename(columns={"平均点": "合計平均点"})
            )
            sum_avg["順序"] = sum_avg["年度"] * 100 + sum_avg["回"]
            sum_avg["表示軸"] = (
                sum_avg["年度"].astype(int).astype(str)
                + "年 第"
                + sum_avg["回"].astype(int).astype(str)
                + "回"
            )

            avg_line = alt.Chart(sum_avg).mark_line(point=True).encode(
                x=alt.X("表示軸:N", sort=alt.SortField("順序")),
                y=alt.Y("合計平均点:Q", title="合計点（平均）"),
                tooltip=["年度", "回", "合計平均点"]
            )
            me_rule = alt.Chart(pd.DataFrame({"自分": [user_total]})).mark_rule(
                color="red", strokeWidth=2
            ).encode(y="自分:Q")

            st.altair_chart(avg_line + me_rule, use_container_width=True)

    # -------- ③ 科目別グラフ --------
    with tab_chart:
        title = "平均点グラフ" if metric == "平均点" else "受験者数グラフ"
        st.subheader("科目別グラフ")

        if not sel_subjs:
            st.info("サイドバーで科目を選んでね")
        else:
            for subj in sel_subjs:
                d = view[view["科目"] == subj].sort_values("順序")

                y_enc = alt.Y(f"{metric}:Q", title=metric)
                if metric == "平均点" and fix_y_to_points:
                    pmax = d["配点"].dropna().max() if "配点" in d.columns else None
                    if pd.notna(pmax):
                        y_enc = alt.Y(
                            f"{metric}:Q",
                            title=metric,
                            scale=alt.Scale(domain=[0, float(pmax)])
                        )

                chart = alt.Chart(d).mark_line(point=True).encode(
                    x=alt.X("表示軸:N", sort=alt.SortField("順序")),
                    y=y_enc,
                    tooltip=["年度", "回", "科目", "平均点", "配点", "受験者数"]
                )
                st.altair_chart(chart, use_container_width=True)



# ======================================================
# 偏差値換算表ビュー
# ======================================================
else:
    st.title("偏差値換算表")

    hensachi_path = HENSACHI_DEFAULT
    if not os.path.exists(hensachi_path):
        st.error("hensachi_facts.csv が見つかりません。管理者に連絡してください。")
        st.stop()

    hensachi = load_hensachi(hensachi_path)

    # =========================
    # サイドバー：条件選択（全部ここ）
    # =========================
    with st.sidebar:
        st.header("条件選択")

        # 学年フィルタ
        if "学年" in hensachi.columns:
            grades = sorted(hensachi["学年"].dropna().unique().tolist())
            sel_grades = st.multiselect("学年", grades, default=grades)
            hensachi = hensachi[hensachi["学年"].isin(sel_grades)]
        else:
            st.info("学年列がないため学年フィルタは表示しません")

        # 年度・回
        years = sorted(hensachi["年度"].dropna().unique().tolist())
        year = st.selectbox("年度", years) if years else None

        times = []
        if year is not None:
            times = sorted(hensachi[hensachi["年度"] == year]["回"].dropna().unique().tolist())
        time_ = st.selectbox("回", times) if times else None

    if year is None or time_ is None:
        st.info("サイドバーで年度と回を選んでね")
        st.stop()

    target = hensachi[(hensachi["年度"] == year) & (hensachi["回"] == time_)].copy()

    # 科目・自分の得点（年度/回で絞った後に作る）
    with st.sidebar:
        subjects = sorted(target["科目"].dropna().unique().tolist())
        sel_subjs = st.multiselect("科目", options=subjects, default=subjects)
        target = target[target["科目"].isin(sel_subjs)]

        st.divider()
        st.subheader("自分の得点")

        subjects2 = sorted(target["科目"].dropna().unique().tolist())
        user_subject = st.selectbox("科目を選択", subjects2) if subjects2 else None

        max_score = 200
        if "得点" in target.columns and target["得点"].notna().any():
            max_score = int(target["得点"].max())

        user_score = st.number_input(
            "得点を入力（整数）",
            min_value=0,
            max_value=max_score,
            value=0,
            step=1
        )

    # =========================
    # メイン：タブ（表 / グラフ＋自分）
    # =========================
    tab_table, tab_graph = st.tabs(
        ["① 偏差値換算表", "② グラフ（自分の換算込み）"]
    )

    # -------- ① 表 --------
    with tab_table:
        st.subheader("偏差値換算表")
        st.dataframe(target, use_container_width=True)

    # -------- ② グラフ＋自分 --------
    with tab_graph:
        st.subheader("得点–偏差値 グラフ（自分の換算込み）")

        # 自分の換算結果を先に表示（同じタブ）
        if user_subject is None or target.empty or target[target["科目"] == user_subject].empty:
            st.info("科目を選ぶと換算結果が表示されます")
            user_h = None
        else:
            user_h = score_to_hensachi(target, user_score, user_subject)
            st.metric("換算された偏差値（目安）", f"{user_h:.1f}")

        if target.empty:
            st.info("表示できるデータがありません（科目選択を確認してね）")
            st.stop()

        base = alt.Chart(target).mark_line(point=True).encode(
            x="得点:Q",
            y="偏差値:Q",
            color="科目:N",
            tooltip=["科目", "得点", "偏差値"]
        )

        hensachi_50 = alt.Chart(pd.DataFrame({"偏差値": [50]})).mark_rule(
            color="gray", strokeDash=[6, 6], strokeWidth=2
        ).encode(y="偏差値:Q")

        layers = [base, hensachi_50]

        # ユーザー点を重ねる
        if user_h is not None:
            user_df = pd.DataFrame([{"科目": user_subject, "得点": user_score, "偏差値": user_h}])

            user_point = alt.Chart(user_df).mark_point(size=120, color="red").encode(
                x="得点:Q",
                y="偏差値:Q",
                tooltip=["科目", "得点", "偏差値"]
            )
            user_rule = alt.Chart(user_df).mark_rule(color="red", strokeWidth=2).encode(x="得点:Q")

            layers += [user_rule, user_point]

        st.altair_chart(alt.layer(*layers), use_container_width=True)
