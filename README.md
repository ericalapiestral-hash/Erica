# 실시간 보이스 체인저 (Real-time Voice Changer)

마이크 입력을 실시간으로 변조해 다시 출력하는 **저부하 피치 시프터**입니다.
무거운 위상 보코더/AI 모델 대신, 모두 NumPy 벡터 연산으로 처리하는
**이중 탭 크로스페이드 딜레이라인** 방식을 사용해 일반 PC에서도 CPU를 거의
잡아먹지 않으면서 자연스러운 음성 변조를 합니다.

## 특징

- ⚡ **저지연**: `sounddevice` 콜백 스트림으로 입력→처리→출력 직결
- 🪶 **저부하**: 단일 코어의 **약 1% 미만**으로 실시간 처리 (벤치마크 기준 ≈0.76%)
- 🎚️ **자연스러움**: 반 윈도우 어긋난 두 탭을 equal-power 크로스페이드해 끊김(클릭) 최소화
- 📦 **가벼운 의존성**: `numpy`, `sounddevice` 두 개뿐

## 설치

```bash
pip install -r requirements.txt
```

> Linux에서는 PortAudio가 필요할 수 있습니다: `sudo apt install libportaudio2`

## 사용법

```bash
# 사용 가능한 오디오 장치 번호 확인
python voice_changer.py --list-devices

# 목소리를 4 반음 올려서 실시간 변조 (기본값)
python voice_changer.py --semitones 4

# 굵고 낮은 목소리 (중저음)
python voice_changer.py --semitones -5

# 한 옥타브 위 (높은 톤)
python voice_changer.py --semitones 12

# 입력/출력 장치를 직접 지정
python voice_changer.py --input 1 --output 3 --semitones 7
```

종료하려면 `Ctrl+C` 를 누르세요.

## 주요 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `-s`, `--semitones` | `4.0` | 피치 변화량(반음). 양수=높게, 음수=낮게, `+12`=1옥타브 |
| `--blocksize` | `256` | 블록 크기(샘플). 작을수록 지연↓ 부하↑ |
| `--window-ms` | `40` | 피치 시프트 윈도우 길이(ms). 길면 안정적, 짧으면 반향↓ |
| `--samplerate` | `44100` | 샘플레이트(Hz) |
| `--gain` | `1.0` | 출력 게인(음량 배수) |
| `--latency` | `low` | 지연 설정: `low`, `high`, 또는 초 단위 숫자 |
| `--input` / `--output` | 자동 | 오디오 장치 번호 (`--list-devices` 로 확인) |

## 동작 원리

피치를 `ratio` 배 올리려면 입력 버퍼를 `ratio` 배 빠르게 읽어야 합니다.
하지만 읽기 포인터가 쓰기 포인터를 따라잡거나 뒤처지므로, 읽기 오프셋을
윈도우 길이 안에서 톱니파처럼 순환시킵니다. 순환 경계에서 생기는 불연속(클릭)은
반 윈도우만큼 어긋난 두 번째 읽기 탭과 **equal-power 크로스페이드**하여 부드럽게
가립니다. 저가형 하드웨어 피치 시프터가 쓰는 고전적이고 CPU 효율이 높은 기법입니다.

> 참고: 순수 사인파에서는 진폭 변조 사이드밴드가 약하게 들릴 수 있으나,
> 배음이 풍부한 실제 사람 목소리에서는 기본 주파수가 정확히 유지되어
> 자연스럽게 들립니다.

## 마이크 출력을 다른 앱(게임/통화)에 넣으려면

`voice_changer.py` 의 출력을 가상 오디오 케이블로 보내면 디스코드/게임 등에서
변조된 목소리를 마이크로 쓸 수 있습니다.

- Windows: [VB-CABLE](https://vb-audio.com/Cable/) 설치 후 `--output` 을 가상 케이블로 지정
- macOS: [BlackHole](https://existential.audio/blackhole/)
- Linux: PulseAudio/PipeWire 의 `null-sink` + `loopback`
