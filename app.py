import streamlit as st
import cv2
from ultralytics import YOLO
import time
import subprocess

# 画面設定
st.set_page_config(page_title="店舗側 - 席状況送信", layout="wide")
st.title("🪑 店舗側 リアルタイム席状況更新システム")

run_camera = st.sidebar.checkbox("カメラを開始", value=False)
frame_placeholder = st.empty()
layout_placeholder = st.empty()

@st.cache_resource
def load_model():
    return YOLO("yolov8n.pt")

model = load_model()

if "last_update_time" not in st.session_state:
    st.session_state.last_update_time = 0
if "last_seats_status" not in st.session_state:
    st.session_state.last_seats_status = []

if "seat_timers" not in st.session_state:
    st.session_state.seat_timers = [
        {"status": True, "last_seen": 0, "is_timer_running": False} for _ in range(4)
    ]

if run_camera:
    # Windows用 DirectShow バックエンドを指定
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    while cap.isOpened() and run_camera:
        success, frame = cap.read()
        if not success:
            st.error("カメラの読み込みに失敗しました。")
            break

        height, width, _ = frame.shape
        area_width = width // 4
        current_ai_detected = [False] * 4

        results = model(frame, stream=True, classes=[0])
        annotated_frame = frame.copy()

        for r in results:
            annotated_frame = r.plot()
            if r.boxes is not None:
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0]
                    center_x = (x1 + x2) / 2
                    idx = int(center_x // area_width)
                    if 0 <= idx < 4:
                        current_ai_detected[idx] = True

        # ⏱️ 5秒間のヒステリシス（誤検知・チラつき防止）
        loop_time = time.time()
        seats_vacant = [True] * 4

        for i in range(4):
            if current_ai_detected[i]:
                st.session_state.seat_timers[i]["status"] = False
                st.session_state.seat_timers[i]["is_timer_running"] = False
            else:
                if not st.session_state.seat_timers[i]["status"] and not st.session_state.seat_timers[i]["is_timer_running"]:
                    st.session_state.seat_timers[i]["last_seen"] = loop_time
                    st.session_state.seat_timers[i]["is_timer_running"] = True
                
                if st.session_state.seat_timers[i]["is_timer_running"]:
                    if loop_time - st.session_state.seat_timers[i]["last_seen"] >= 5:
                        st.session_state.seat_timers[i]["status"] = True
                        st.session_state.seat_timers[i]["is_timer_running"] = False
            
            seats_vacant[i] = st.session_state.seat_timers[i]["status"]

        # UIレイアウト表示
        with layout_placeholder.container():
            st.subheader("🗺️ カウンター席レイアウト（1列4席）")
            cols = st.columns(4)
            for i in range(4):
                with cols[i]:
                    if not seats_vacant[i]:
                        st.error(f"🟥 席 {i+1}\n\n満席")
                    else:
                        st.success(f"🟩 席 {i+1}\n\n空席")
            st.info(f"📊 現在の空席数: **4席中 {seats_vacant.count(True)} 席**")

        # 🎯 状態変更時または30秒ごとに GitHub へ自動 Push
        current_time = time.time()
        if seats_vacant != st.session_state.last_seats_status or (current_time - st.session_state.last_update_time > 30):
            with open("status.txt", "w", encoding="utf-8") as f:
                f.write(f"{', '.join([str(s) for s in seats_vacant])}\n{time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                subprocess.run(["git", "add", "status.txt"], check=True)
                subprocess.run(["git", "commit", "-m", "Update seat status [auto]"], check=True)
                subprocess.run(["git", "push"], check=True)
                print(f"[{time.strftime('%H:%M:%S')}] GitHubへ同期完了")
            except Exception as e:
                print(f"Git Push エラー: {e}")
                
            st.session_state.last_seats_status = seats_vacant.copy()
            st.session_state.last_update_time = current_time

        annotated_frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(annotated_frame_rgb, channels="RGB")

    cap.release()
    frame_placeholder.empty()
    layout_placeholder.empty()