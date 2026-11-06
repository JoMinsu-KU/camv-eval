# CAMV-Eval v14 추가 재현 자료

최신 원고 **Threshold Calibration and Bootstrap Inference for Multi-View Grasp Verification**, v14.3에 대응한다. 저자 다섯 명과 기여 정보는 유지한다. 기존 v8·v12 릴리스를 보존하고 v14의 새 수치 자료를 별도 릴리스로 제공한다.

```text
gh release download v14-repro-1 --repo JoMinsu-KU/camv-eval --pattern CAMV-Eval_v14_Reproduction.zip --dir ../v14-assets
python -m pip install -r requirements-v14.txt
python reproduce_v14.py --asset ../v14-assets/CAMV-Eval_v14_Reproduction.zip --output ../v14-replay --fresh-first
```

출력 경로는 아직 없는 저장소 밖 폴더로 지정한다. 새 E1의 저장 점수·배열 재계산과 일부 결정적 재생성을 수행하며, GPU·원본 이미지·모델 가중치는 필요하지 않다. 독립 outer 데이터셋 2,000개가 bare/space를 공유하여 scorer별 저장 기록은 4,000개다. A1–A7 표는 별도 감사 결과 snapshot이며 원시 입력 전체의 재실행으로 표현하지 않는다. [v14 재현 안내](docs/REPRODUCIBILITY-v14.md)와 [새 결과 CSV](results/v14)를 참고한다.

아래 문서는 이전 v8·v12 자료와 v13 편집본의 이력을 설명한다. 아래의 Table 번호와 원고 제목은 해당 이전 버전에 속한다.

---

# 원고 v13–v13.4.5와 수치 자료 대응

원고 v13–v13.4.5는 기존 v8·v12 수치 자료를 유지한 해석·표현·선언 및 편집 수정본이다. 추가 실험이나 모델 추론은 없다. [버전 대응표](docs/MANUSCRIPT_VERSION_MAP.md)와 [편집 이력](docs/EDITORIAL_HISTORY.md)을 참고한다. N02/FSR 개발 분산 비율의 원값은 0.9084945668118725이며 표와 본문에는 0.908로 표시한다.

# v12 추가 자료 안내

v12-repro-1에는 추가 시뮬레이션 3조건과 저장 자료 재분석을 담았다. 기존 v8 결과와 네 개 검정은 유지했다. 새 수치 ZIP을 릴리스에서 내려받고 `docs/REPRODUCIBILITY-v12.md`의 명령으로 재현할 수 있다. 아래 기존 재현 안내는 v8 원본 결과에 해당한다.

# CAMV-Eval 재현 패키지

Minsu Jo, Namhyun Yoo, Beomseok Kim, Hoansuk Choi, Jinhong Yang의 원고 **Calibration and Bootstrap Inference for Multi-View Grasp Verification**, v13.4.5를 지원한다. 수치 근거는 공개된 v8·v12 릴리스에 보존되어 있다.

저자 순서와 실제 연구 기여는 [저자·기여 안내](docs/AUTHORS.md)에 정리했다.

## 간단 재현

Python 3.11 환경에서 저장소 폴더로 이동한 뒤 실행한다.

```powershell
python -m pip install -r requirements-quick.txt
python reproduce.py --mode quick --output ../camv-quick
```

Table 5의 8개 지표에 대해 원래 부트스트랩 배열에서 점추정치·conditional/refit 구간을 다시 계산한다. 기존 요약과 64개 필드를 대조하며, CSV와 표 행이 동일해야 통과한다. NumPy만 필요하고 예제 입력은 저장소에 포함되어 있다.

## 전체 수치 재현

```powershell
python -m pip install -r requirements.txt
python reproduce.py --mode all --assets-dir ../release-assets --output ../camv-full
```

공개된 [v8-repro-1 릴리스](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v8-repro-1)의 ZIP 3개를 저장소 밖 `release-assets/` 폴더에 내려받는다. 다음 명령으로 다운로드와 크기·SHA-256 검증을 함께 수행할 수도 있다.

```powershell
python fetch_assets.py --repository JoMinsu-KU/camv-eval --tag v8-repro-1 --output ../release-assets
```

v12 추가 분석은 [v12 재현 안내](docs/REPRODUCIBILITY-v12.md)의 별도 명령을 따른다.

출력 폴더는 **아직 존재하지 않는 저장소 밖 경로**로 지정한다. 계산이 다 끝나면 그 안의 `completion.json`에서 `status: PASS`를 확인한다. 단계별 로그는 `logs/`에 기록된다. 기존 출력 폴더를 덮어쓰지 않는다.

이 명령은 저장 점수에서 임계값과 원래 실증 분석을 다시 계산하고, 시뮬레이션 저장 배열의 요약과 제한된 결정적 재생성을 수행한다. 전체 VLM 추론이나 모든 Monte Carlo 반복을 새로 수행하는 명령은 아니다. GPU·모델 가중치·원본 이미지·API 키 없이 실행한다. [정확한 재현 범위](REPRODUCIBILITY.md)에 단계별 차이를 적었다.

## 결과 확인

- [51개 표를 한 문서에서 보기](docs/ALL_TABLES.md): 본문 8개와 보충표 43개, 표 각주 포함.
- `results/tables/`: 각 표의 CSV. 원고 표시값을 내보낸 것으로, 새 계산 결과와 구분한다.
- `code/`: 해시가 보존된 원래 분석 코드.
- `provenance/verification.json`: 이번 패키지 검증 결과.
- [GitHub 업로드 안내](docs/UPLOAD.ko.md): 작은 코드 저장소와 큰 Release 첨부파일의 구분.

저자 소유 코드는 MIT 라이선스다. 외부 데이터·모델에는 원래 조건이 적용된다. 원본 이미지·모델 가중치·저자 사진은 포함하지 않는다. 이 문서는 공개된 저장소와 v8·v12 수치 재현 릴리스의 사용 안내다.
