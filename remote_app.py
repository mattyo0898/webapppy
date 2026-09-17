import streamlit as st
import requests
import time

st.set_page_config(page_title="リアルタイム席状況", page_icon="🪑", layout="centered")
st.title("🪑 店舗 空席状況（リアルタイム）")

# 🌐 GitHub上の status.txt Raw URL（公開リポジトリ用）
STATUS_URL = "https://raw.githubusercontent.com/poi9/webapppy/main/status.txt"

# キャッシュ回避用のタイムスタンプ付与
url_with_param = f"{STATUS_URL}?t={int(time.time())}"

try:
    response = requests.get(url_with_param, timeout=5)
    
    if response.status_code == 200:
        lines = response.text.strip().split("\n")
        
        if len(lines) >= 1:
            raw_statuses = [s.strip() for s in lines[0].split(",")]
            seats_status = [status == "True" for status in raw_statuses]
            updated_time = lines[1] if len(lines) > 1 else "不明"
            
            st.subheader("現在の空席状況（1列4席）")
            cols = st.columns(4)
            
            for i in range(min(4, len(seats_status))):
                with cols[i]:
                    if seats_status[i]:
                        st.success(f"🟩 席 {i+1}\n\n**空席**")
                    else:
                        st.error(f"🟥 席 {i+1}\n\n**満席**")
            
            vacant_count = seats_status.count(True)
            st.info(f"📊 現在 **4席中 {vacant_count} 席** が空いています（最終更新: {updated_time}）")
        else:
            st.warning("データ形式が正しくありません。")
    else:
        st.error(f"データ取得失敗 (HTTPステータス: {response.status_code})")

except Exception as e:
    st.error(f"接続エラー: {e}")

# 5秒ごとに自動再取得
time.sleep(5)
st.rerun()