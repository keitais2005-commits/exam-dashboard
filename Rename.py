import os
import re

folder = "/Users/keita/Desktop/DS_Top_M_Streamlit/All_Data/S6_Gouhan_PDF/"
DRY_RUN = False  # ← 確認後 False にする　確認前はTrue 

for file in os.listdir(folder):
    if not file.endswith(".pdf"):
        continue

    old_path = os.path.join(folder, file)

    # YYYY-0-回-xxx.pdf → YYYY-回-xxx.pdf
    new_name = re.sub(r"^(\d{4})-0-(\d+)-", r"\1-\2-", file)

    if new_name == file:
        print(f"（変更なし）{file}")
        continue

    new_path = os.path.join(folder, new_name)

    if os.path.exists(new_path):
        print(f"⚠ 既に存在: {new_name}（スキップ）")
        continue

    print(f"✔ {file} → {new_name}")
    if not DRY_RUN:
        os.rename(old_path, new_path)
