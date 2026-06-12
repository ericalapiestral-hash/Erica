import time
import pyautogui
import keyboard
import mss
import numpy as np

# ================= [ 설정 영역 ] =================
REPEAT_CLICK_X, REPEAT_CLICK_Y = 920, 358

# mss 라이브러리는 region 대신 top, left, width, height를 사용합니다.
REGION = {"top": 180, "left": 95, "width": 517, "height": 292}

# 목표 분홍색 RGB 값 (mss/OpenCV는 기본적으로 BGR 패턴을 쓰므로 맞춰서 타겟 설정)
# 여기서는 편의상 RGB로 두고 코드 내에서 변환하겠습니다.
TARGET_PINK_RGB = (255, 138, 180)
TOLERANCE = 20

ACTION_CLICK_X, ACTION_CLICK_Y = 833, 676
EXIT_KEY = 'f4'
# =================================================

print("🚀 초고속 영역 감지 매크로를 시작합니다. (MSS + NumPy 적용)")
print(f"🛑 종료하려면 [{EXIT_KEY.upper()}] 키를 누르세요.")
print("-" * 50)

# 효율적인 비교를 위해 오차 범위 배열 생성
lower_bound = np.array([max(0, c - TOLERANCE) for c in TARGET_PINK_RGB])
upper_bound = np.array([min(255, c + TOLERANCE) for c in TARGET_PINK_RGB])

try:
    with mss.mss() as sct:
        while True:
            # 1. 종료 단축키 체크
            if keyboard.is_pressed(EXIT_KEY):
                print(f"\n🛑 단축키 입력으로 종료합니다.")
                break

            # 2. 평소 기본 좌표 클릭 (대기 시간 최소화)
            pyautogui.click(REPEAT_CLICK_X, REPEAT_CLICK_Y)
            time.sleep(0.01) # 0.1초에서 0.01초로 줄여 반응성 극대화

            # 3. MSS를 이용한 초고속 화면 캡처 (0.005초 내외)
            scr = sct.grab(REGION)
            
            # 4. 이미지 데이터를 NumPy 배열로 변경 (BGRA -> RGB 변환)
            img_np = np.array(scr)[:, :, :3] # Alpha 채널 제거
            img_rgb = img_np tyranny = img_np[:, :, ::-1] # BGR을 RGB로 뒤집기

            # 5. NumPy 브로드캐스팅을 이용해 for 문 없이 한 번에 색상 매칭 검사
            mask = np.all((img_rgb >= lower_bound) & (img_rgb <= upper_bound), axis=-1)
            
            if np.any(mask): # 만족하는 픽셀이 하나라도 있다면!
                print("🌸 영역 내에서 분홍색 감지 성공! -> 목표 클릭 수행")
                pyautogui.click(ACTION_CLICK_X, ACTION_CLICK_Y)
                
                # 중복 클릭 방지 대기
                time.sleep(2.0)

except KeyboardInterrupt:
    print("\n👋 터미널 입력으로 프로그램을 안전하게 종료했습니다.")
except pyautogui.FailSafeException:
    print("\n🚨 마우스가 화면 모서리로 이동하여 강제 종료되었습니다.")