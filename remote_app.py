import base64
import time
import requests
import streamlit as st

# ページ基本設定
st.set_page_config(
    page_title="座席空き状況（店舗用）", page_icon="🪑", layout="centered"
)
st.title("🪑 リアルタイム座席空き状況")

# GitHub APIのURL（RawではなくAPI経由にすることでキャッシュの影響を受けなくする）
API_URL = "https://api.github.com/repos/mattyo0898/webapppy/contents/status.txt"


def fetch_seat_status():
    """GitHub API経由で status.txt の最新状態を取得（Base64デコード対応）"""
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Cache-Control": "no-cache",
        }
        # タイムスタンプを付与してキャッシュを完全に回避
        response = requests.get(
            f"{API_URL}?t={int(time.time())}", headers=headers, timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            # GitHub APIは中身をBase64で返してくるのでデコードする
            file_content = base64.b64decode(data["content"]).decode("utf-8")
            lines = file_content.strip().split("\n")

            if len(lines) >= 1:
                # "True, False, True, False" を bool値のリストに変換
                status_list = [
                    s.strip().lower() == "true" for s in lines[0].split(",")
                ]
                last_updated = lines[1] if len(lines) > 1 else "不明"
                return status_list, last_updated
    except Exception as e:
        st.error(f"データ取得エラー: {e}")

    return [True] * 4, "取得失敗"


# 最新状態を取得
statuses, last_updated_time = fetch_seat_status()

# 最終更新日時の表示
st.caption(f"最終更新時刻: {last_updated_time}")

# 座席表示（2×2レイアウト）
col1, col2 = st.columns(2)

with col1:
    st.subheader("席 1")
    if statuses[0]:
        st.success("🟢 空席")
    else:
        st.error("🔴 使用中")

    st.subheader("席 3")
    if len(statuses) > 2 and statuses[2]:
        st.success("🟢 空席")
    else:
        st.error("🔴 使用中")

with col2:
    st.subheader("席 2")
    if len(statuses) > 1 and statuses[1]:
        st.success("🟢 空席")
    else:
        st.error("🔴 使用中")

    st.subheader("席 4")
    if len(statuses) > 3 and statuses[3]:
        st.success("🟢 空席")
    else:
        st.error("🔴 使用中")

st.divider()

# 画面最下部に自動更新のインジケーターを表示しつつ10秒待機
with st.spinner("リアルタイム同期中...（10秒ごとに自動更新）"):
    time.sleep(10)

# 強制再起動（ループ処理）
st.rerun()
