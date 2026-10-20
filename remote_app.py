import datetime
import time
import cv2
import numpy as np
import requests
import streamlit as st

# ページ基本設定
st.set_page_config(
    page_title="店舗リアルタイム座席状況",
    page_icon="🪑",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# JavaScript/HTMLによる3秒ごとの強制自動リロード（Streamlit Cloud対応）
st.components.v1.html(
    """
    <script>
        setTimeout(function(){
            window.parent.postMessage({type: 'streamlit:rerun'}, '*');
        }, 3000);
    </script>
    """,
    height=0,
)

st.title("店舗リアルタイム座席状況（間取り図）")

# 1. GitHub Raw ファイル取得設定
STATUS_URL = (
    "https://raw.githubusercontent.com/mattyo0898/webapppy/main/status.txt"
)


def fetch_latest_status():
    """GitHubから最新の status.txt を取得（キャッシュ破棄処理付き）"""
    try:
        # キャッシュバスター（URLにタイムスタンプを付与）
        cache_buster_url = f"{STATUS_URL}?t={int(time.time())}"
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        response = requests.get(cache_buster_url, headers=headers, timeout=3)

        if response.status_code == 200:
            lines = response.text.strip().split("\n")
            if lines and len(lines) >= 1:
                status_line = lines[0]
                time_line = lines[1] if len(lines) > 1 else "日時情報なし"

                # 'True' / 'False' の文字列を bool 値に変換
                statuses = [
                    s.strip().lower() == "true" for s in status_line.split(",")
                ]

                while len(statuses) < 4:
                    statuses.append(True)

                return statuses[:4], time_line
    except Exception as e:
        st.error(f"データ取得エラー: {e}")

    return [True, True, True, True], "データ取得失敗"


# 2. 最新データの取得
seat_statuses, last_updated_time = fetch_latest_status()

# 最終更新日時の表示
st.caption(f"最終同期日時: {last_updated_time}")

# 3. レイアウト・間取り図表示セクション
st.subheader("座席配置レイアウト")

# 4列のレイアウトで各座席のステータスを表示
cols = st.columns(4)

for idx, is_empty in enumerate(seat_statuses):
    with cols[idx]:
        if is_empty:
            st.success(f"### Seat {idx + 1}\n\n🟢 **空席**")
        else:
            st.error(f"### Seat {idx + 1}\n\n🔴 **使用中**")

st.divider()

# 視覚的な間取り図ブロックの描画（背景グラフィック表示）
floor_plan = np.full((200, 640, 3), 245, dtype=np.uint8)
w_quarter = 640 // 4

for i in range(4):
    x1 = i * w_quarter
    x2 = (i + 1) * w_quarter

    color = (100, 200, 100) if seat_statuses[i] else (100, 100, 230)

    cv2.rectangle(floor_plan, (x1 + 10, 20), (x2 - 10, 180), color, -1)
    cv2.rectangle(floor_plan, (x1 + 10, 20), (x2 - 10, 180), (50, 50, 50), 2)

    label_text = f"Seat {i + 1}"
    status_text = "EMPTY" if seat_statuses[i] else "OCCUPIED"

    cv2.putText(
        floor_plan,
        label_text,
        (x1 + 25, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        floor_plan,
        status_text,
        (x1 + 20, 120),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )

# 間取り図画像の表示（width="stretch" で非推奨警告を防止）
floor_plan_rgb = cv2.cvtColor(floor_plan, cv2.COLOR_BGR2RGB)
st.image(
    floor_plan_rgb,
    caption="店舗リアルタイム間取りレイアウト",
    width="stretch",
)
