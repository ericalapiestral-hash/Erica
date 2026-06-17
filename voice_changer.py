"""
실시간 보이스 체인저 (Real-time Voice Changer)
==============================================

특징
----
- 저지연(real-time): sounddevice 콜백 스트림으로 마이크 입력을 바로 처리해 출력
- 저부하(CPU 친화): 무거운 FFT/위상 보코더 대신, 이중 탭 크로스페이드 딜레이라인
  방식(그래뉼러 피치 시프트)을 사용. 모든 연산이 NumPy 벡터 연산이라 한 코어의
  몇 % 만으로도 동작
- 자연스러움: 두 개의 읽기 탭을 반 윈도우만큼 어긋나게 두고 equal-power 크로스페이드
  하여 피치를 옮길 때 생기는 끊김(클릭)을 부드럽게 무마

원리
----
피치를 ratio 배로 올리려면 입력을 ratio 배 빠르게 읽어야 한다. 하지만 그러면 읽기
포인터가 쓰기 포인터를 따라잡거나 뒤처지므로, 읽기 오프셋을 윈도우 길이 안에서
톱니파처럼 순환시키고, 순환 경계의 불연속을 가리기 위해 반 윈도우 어긋난 두 번째
탭과 크로스페이드한다. (저가형 하드웨어 피치 시프터에서 쓰는 고전적 기법)

사용법
------
    pip install -r requirements.txt

    # 사용 가능한 오디오 장치 확인
    python voice_changer.py --list-devices

    # 목소리를 4 반음 올려서 실시간 변조 (기본값)
    python voice_changer.py --semitones 4

    # 낮은 목소리 (괴물/중저음)
    python voice_changer.py --semitones -5

    # 입력/출력 장치를 직접 지정
    python voice_changer.py --input 1 --output 3 --semitones 7

종료: Ctrl+C
"""

import argparse
import sys

import numpy as np
import sounddevice as sd


class PitchShifter:
    """이중 탭 크로스페이드 딜레이라인 기반의 저부하 실시간 피치 시프터.

    블록 단위로 호출되며 내부에 직전 블록의 꼬리(tail)와 오프셋 위상(state)을
    유지해 블록 경계에서도 연속적으로 동작한다.
    """

    def __init__(self, semitones: float, samplerate: int, window_ms: float = 40.0):
        self.samplerate = samplerate
        # 윈도우(그래뉼) 길이. 길수록 음정은 안정적이지만 반향(겹침)이 늘어난다.
        self.window = max(256, int(samplerate * window_ms / 1000.0))
        # 보간을 위한 여유 margin 을 둔 꼬리 버퍼 길이
        self.tail_len = self.window + 4
        self.tail = np.zeros(self.tail_len, dtype=np.float32)
        # 현재 읽기 오프셋(쓰기 위치 기준 과거 방향). 0 ~ window 사이를 순환.
        self.offset = 0.0
        self.set_semitones(semitones)

    def set_semitones(self, semitones: float) -> None:
        """피치 변화량을 반음 단위로 설정 (실시간 변경 가능)."""
        self.semitones = float(semitones)
        # +12 반음 = 1 옥타브 = 2배 주파수
        self.ratio = 2.0 ** (self.semitones / 12.0)

    def process(self, x: np.ndarray) -> np.ndarray:
        """모노 float32 블록을 받아 변조된 모노 float32 블록을 반환."""
        n = x.shape[0]

        # 피치 변화가 없으면 그대로 통과 (불필요한 연산/지연 제거)
        if abs(self.semitones) < 1e-6:
            self.tail = np.concatenate([self.tail, x])[-self.tail_len:]
            return x.copy()

        window = self.window
        base = self.tail_len  # data 안에서 "현재 쓰기 위치"의 기준 인덱스
        data = np.concatenate([self.tail, x])  # 길이 = tail_len + n

        i = np.arange(n, dtype=np.float32)
        step = self.ratio - 1.0  # 매 샘플마다 오프셋이 줄어드는(또는 느는) 양

        # 두 탭의 순환 오프셋 (0 ~ window)
        off1 = np.mod(self.offset - i * step, window)
        off2 = np.mod(off1 + window * 0.5, window)

        out = self._read_tap(data, base, i, off1, window) \
            + self._read_tap(data, base, i, off2, window)

        # 다음 블록을 위한 상태 갱신
        self.offset = float(np.mod(self.offset - n * step, window))
        self.tail = data[-self.tail_len:]

        return out.astype(np.float32)

    @staticmethod
    def _read_tap(data, base, i, off, window):
        """data 에서 분수 위치를 선형보간으로 읽고 equal-power 게인을 적용."""
        pos = base + i - off                      # 읽을 분수 인덱스
        idx0 = np.floor(pos).astype(np.int64)
        idx0 = np.clip(idx0, 0, data.shape[0] - 2)
        frac = (pos - idx0).astype(np.float32)
        sample = data[idx0] * (1.0 - frac) + data[idx0 + 1] * frac

        # 윈도우 경계(off=0, off=window)에서 0, 가운데에서 1 인 사인 페이드
        gain = np.sin(np.pi * (off / window)).astype(np.float32)
        return sample * gain


def list_devices() -> None:
    print(sd.query_devices())


def run(args) -> None:
    samplerate = args.samplerate
    shifter = PitchShifter(args.semitones, samplerate, window_ms=args.window_ms)

    print("🎙️  실시간 보이스 체인저를 시작합니다.")
    print(f"    피치: {args.semitones:+.1f} 반음 (ratio={shifter.ratio:.3f})")
    print(f"    샘플레이트: {samplerate} Hz / 블록: {args.blocksize} 샘플")
    print(f"    윈도우: {shifter.window} 샘플 ({args.window_ms:.0f} ms)")
    print("    종료하려면 Ctrl+C 를 누르세요.")
    print("-" * 50)

    def callback(indata, outdata, frames, time_info, status):
        if status:
            # 언더런/오버런 등은 표준 에러로만 표시 (실시간 흐름은 끊지 않음)
            print(status, file=sys.stderr)
        # 입력이 스테레오여도 음성은 모노로 처리해 부하를 줄인 뒤 출력 채널에 복제
        mono = indata[:, 0]
        wet = shifter.process(mono)
        wet = wet * args.gain
        np.clip(wet, -1.0, 1.0, out=wet)
        outdata[:] = wet[:, np.newaxis]

    try:
        with sd.Stream(
            samplerate=samplerate,
            blocksize=args.blocksize,
            dtype="float32",
            channels=1,
            latency=args.latency,
            device=(args.input, args.output),
            callback=callback,
        ):
            # 콜백 스레드가 오디오를 처리하는 동안 메인 스레드는 대기
            import threading
            threading.Event().wait()
    except KeyboardInterrupt:
        print("\n👋 보이스 체인저를 종료했습니다.")
    except Exception as exc:  # 장치/포맷 문제 등을 친절히 안내
        print(f"\n🚨 오류: {exc}", file=sys.stderr)
        print("    '--list-devices' 로 장치 번호를 확인한 뒤 '--input/--output' 으로 지정해 보세요.",
              file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="저부하 실시간 보이스 체인저 (피치 시프트)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--list-devices", action="store_true",
                   help="사용 가능한 오디오 입출력 장치 목록 출력 후 종료")
    p.add_argument("-s", "--semitones", type=float, default=4.0,
                   help="피치 변화량(반음). 양수=높게, 음수=낮게. +12=1옥타브")
    p.add_argument("--samplerate", type=int, default=44100, help="샘플레이트(Hz)")
    p.add_argument("--blocksize", type=int, default=256,
                   help="블록 크기(샘플). 작을수록 지연↓ 부하↑")
    p.add_argument("--window-ms", type=float, default=40.0,
                   help="피치 시프트 윈도우 길이(ms). 길면 안정적, 짧으면 반향↓")
    p.add_argument("--gain", type=float, default=1.0, help="출력 게인(음량 배수)")
    p.add_argument("--latency", default="low",
                   help="지연 설정: 'low', 'high' 또는 초 단위 숫자")
    p.add_argument("--input", type=int, default=None, help="입력 장치 번호")
    p.add_argument("--output", type=int, default=None, help="출력 장치 번호")
    return p


def main() -> None:
    args = build_parser().parse_args()

    # latency 인자가 숫자면 float 로 변환
    if isinstance(args.latency, str):
        try:
            args.latency = float(args.latency)
        except ValueError:
            pass

    if args.list_devices:
        list_devices()
        return

    run(args)


if __name__ == "__main__":
    main()
