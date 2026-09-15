# CAMV-Eval 재현 패키지

Minsu Jo, Namhyun Yoo, Jinhong Yang의 원고 **Calibration and Bootstrap Inference for Multi-View Grasp Verification**, v8에 대응한다.

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

제작된 전체 전달 ZIP을 풀면 `repository/`와 `release-assets/`가 나란히 있다. `repository/`에서 위 명령을 실행하면 다운로드 없이 작동한다. GitHub에서 코드를 받은 이용자는 해당 Release의 ZIP 3개를 별도 폴더에 내려받으면 된다. 실제 공개 후에는 `fetch_assets.py`에 저장소 주소를 지정하여 받을 수도 있다.

출력 폴더는 **아직 존재하지 않는 저장소 밖 경로**로 지정한다. 계산이 다 끝나면 그 안의 `completion.json`에서 `status: PASS`를 확인한다. 단계별 로그는 `logs/`에 기록된다. 기존 출력 폴더를 덮어쓰지 않는다.

이 명령은 저장 점수에서 임계값과 원래 실증 분석을 다시 계산하고, 시뮬레이션 저장 배열의 요약과 제한된 결정적 재생성을 수행한다. 전체 VLM 추론이나 모든 Monte Carlo 반복을 새로 수행하는 명령은 아니다. GPU·모델 가중치·원본 이미지·API 키 없이 실행한다. [정확한 재현 범위](REPRODUCIBILITY.md)에 단계별 차이를 적었다.

## 결과 확인

- [51개 표를 한 문서에서 보기](docs/ALL_TABLES.md): 본문 8개와 보충표 43개, 표 각주 포함.
- `results/tables/`: 각 표의 CSV. 원고 표시값을 내보낸 것으로, 새 계산 결과와 구분한다.
- `code/`: 해시가 보존된 원래 분석 코드.
- `provenance/verification.json`: 이번 패키지 검증 결과.
- [GitHub 업로드 안내](docs/UPLOAD.ko.md): 작은 코드 저장소와 큰 Release 첨부파일의 구분.

저자 소유 코드는 MIT 라이선스다. 외부 데이터·모델에는 원래 조건이 적용된다. 원본 이미지·모델 가중치·저자 사진은 포함하지 않는다. 현재 문서는 공개를 준비한 패키지의 안내이며 실제 GitHub 업로드나 논문 게재를 의미하지 않는다.
