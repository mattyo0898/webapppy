import base64
import datetime
import threading
import time
import cv2
import requests
import streamlit as st
from ultralytics import YOLO

# ページ基本設定
st.set_page_config(page_title="店舗座席監視", layout="wide")
st.title("店舗リアルタイム座席監視システム")

# 1. GitHub API 設定（最新のトークンを指定）
GITHUB_TOKEN = "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"
REPO_OWNER = "mattyo0898"
REPO_NAME = "webapppy"
FILE_PATH = "status.txt"


def update_status_github_sync(statuses):
    """GitHubへ status.txt を更新送信（ターミナルへ結果ログ表示）"""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_str = ", ".join(["True" if s else "False" for s in statuses])
    content_text = f"{status_str}\n{now_str}"

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        # 既存ファイルの SHA を取得
        get_res = requests.get(url, headers=headers, timeout=5)
        sha = ""
        if get_res.status_code == 200:
            sha = get_res.json().get("sha", "")
        elif get_res.status_code == 401:
            print(
                f"[{now_str}] ❌ 認証エラー (401): トークンが無効です。新しいトークンを貼り直してください。"
            )
            return
        elif get_res.status_code == 404:
            print(
                f"[{now_str}] ⚠️ status.txt が見つかりません。新規作成します。"
            )

        # Base64エンコード
        encoded_content = base64.b64encode(content_text.encode("utf-8")).decode(
            "utf-8"
        )

        data = {
            "message": f"Auto update status: {now_str}",
            "content": encoded_content,
            "branch": "main",
        }
        if sha:
            data["sha"] = sha

        # GitHub APIへ更新リクエスト
        put_res = requests.put(url, headers=headers, json=data, timeout=5)

        if put_res.status_code in [200, 201]:
            print(
                f"[{now_str}] ✅ GitHub更新成功！ 座席状態: [{status_str}]"
            )
        else:
            print(
                f"[{now_str}] ❌ 送信失敗 Status Code: {put_res.status_code}, レスポンス: {put_res.text}"
            )

    except Exception as e:
        print(f"[{now_str}] ❌ 通信エラー: {e}")


def send_to_github_in_background(statuses):
    """メインループを止めないためにバックグラウンドスレッドで送信"""
    thread = threading.Thread(
        target=update_status_github_sync, args=(statuses.copy(),)
    )
    thread.daemon = True
    thread.start()


# 離席判定のディレイ設定（5秒）
EMPTY_DELAY_SECONDS = 5.0


def main():
    st.sidebar.header("コントロール")
    run_system = st.sidebar.checkbox("監視システム起動", value=False)

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("カメラ映像")
        image_placeholder = st.empty()

    with col2:
        st.subheader("座席状況")
        status_placeholders = [st.empty() for _ in range(4)]

    if not run_system:
        st.info(
            "左側のサイドバーから「監視システム起動」にチェックを入れるとカメラが始動します。"
        )
        return

    @st.cache_resource
    def load_yolo():
        return YOLO("yolov8n.pt")

    model = load_yolo()
    cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        st.error("カメラが開けません。")
        return

    last_update_time = 0
    frame_count = 0

    seat_detected_empty_time = [None] * 4
    seat_current_statuses = [True] * 4
    people_boxes = []

    while run_system and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        height, width, _ = frame.shape
        w_quarter = width // 4

        # 4つの座席領域を設定
        seats_roi = [
            [0, 0, w_quarter, height],
            [w_quarter, 0, w_quarter * 2, height],
            [w_quarter * 2, 0, w_quarter * 3, height],
            [w_quarter * 3, 0, width, height],
        ]

        frame_count += 1

        # 3フレームに1回 YOLO推論（軽量化のため320x240にリサイズ）
        if frame_count % 3 == 0:
            small_frame = cv2.resize(frame, (320, 240))
            results = model(small_frame, verbose=False, conf=0.5)
            boxes = results[0].boxes

            people_boxes = []
            if boxes is not None:
                for box in boxes:
                    if int(box.cls[0]) == 0:  # 人(person)の検出
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        people_boxes.append([x1 * 2, y1 * 2, x2 * 2, y2 * 2])

        now_time = time.time()

        # 座席ごとの着席・離席判定
        for seat_id, seat in enumerate(seats_roi):
            sx1, sy1, sx2, sy2 = seat
            person_in_seat = False

            for px1, py1, px2, py2 in people_boxes:
                center_x = (px1 + px2) // 2
                if sx1 <= center_x < sx2:
                    person_in_seat = True
                    break

            if person_in_seat:
                seat_current_statuses[seat_id] = False
                seat_detected_empty_time[seat_id] = None
            else:
                if seat_current_statuses[seat_id] is False:
                    if seat_detected_empty_time[seat_id] is None:
                        seat_detected_empty_time[seat_id] = now_time
                    elif (
                        now_time - seat_detected_empty_time[seat_id]
                        >= EMPTY_DELAY_SECONDS
                    ):
                        seat_current_statuses[seat_id] = True
                        seat_detected_empty_time[seat_id] = None

        # 右側カラムに現在の座席状態（テキスト）を表示
        for idx, is_empty in enumerate(seat_current_statuses):
            if is_empty:
                status_placeholders[idx].success(f"Seat {idx + 1}: 🟢 空席")
            else:
                status_placeholders[idx].error(f"Seat {idx + 1}: 🔴 使用中")

        # カメラ映像に座席枠線を描画
        for seat_id, seat in enumerate(seats_roi):
            sx1, sy1, sx2, sy2 = seat
            cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), (255, 255, 255), 2)
            cv2.putText(
                frame,
                f"Seat {seat_id + 1}",
                (sx1 + 10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

        # 検出された人に青いバウンディングボックスを描画
        for px1, py1, px2, py2 in people_boxes:
            cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 0, 0), 2)
            cv2.putText(
                frame,
                "person",
                (px1, max(20, py1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 0, 0),
                2,
            )

        # 3秒周期で GitHub へバックグラウンド送信
        if now_time - last_update_time >= 10:
            send_to_github_in_background(seat_current_statuses)
            last_update_time = now_time

        # Streamlit 画面の更新
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_placeholder.image(
            frame_rgb, channels="RGB", width="stretch"
        )

    cap.release()


if __name__ == "__main__":
    main()
