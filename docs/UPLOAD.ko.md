# GitHub 업로드 안내

이 문서는 업로드할 파일의 위치와 순서를 설명한다. 이번 패키지 제작 단계에서는 원격 저장소 생성·git push·Release 공개를 실행하지 않았다.

## 1. 코드 저장소에 넣을 파일

전체 전달 ZIP을 풀면 아래와 같이 나온다.

```text
CAMV-Eval-GitHub-v8/
  repository/       GitHub 코드 저장소의 루트로 사용할 내용
  release-assets/   GitHub Release에 첨부할 큰 ZIP 3개
  START-HERE.ko.md
```

GitHub에 빈 저장소를 만들고, **repository 폴더 안의 파일과 하위 폴더**를 저장소 루트에 올린다. `repository/`를 다시 한 겹 감싸지 않는 편이 README와 실행 명령을 바로 보기에 좋다. README, MIT LICENSE, CITATION.cff, 숨김 파일 `.gitattributes`와 `.gitignore`도 함께 올린다.

Git을 사용한다면 `repository/`에서 아래를 실행한다. `실제주소`는 생성한 저장소의 HTTPS 주소로 바꾼다. 명령을 제공할 뿐 자동 실행하지 않는다.

```powershell
git init -b main
git add .
git commit -m "Add CAMV-Eval v8 numerical reproduction package"
git remote add origin 실제주소
git push -u origin main
```

`.gitattributes`는 체크아웃 시 줄바꿈 변환을 막는다. 원래 코드 및 수치 파일의 SHA-256 검증을 위해 필요하다. 테스트·다운로드·출력 디렉터리와 환경 폴더를 Git에 추가하지 않는다.

## 2. 큰 수치 자료는 Release에 첨부

GitHub의 **Releases → Draft a new release**에서 태그 `v8-repro-1`을 사용하고 `release-assets/` 안의 ZIP 3개를 그대로 첨부한다. 파일명은 `assets.json`과 일치해야 한다. [RELEASE_NOTES.md](RELEASE_NOTES.md)를 설명으로 사용할 수 있다.

GitHub는 일반 Git 파일의 100 MiB 초과 업로드를 차단하므로, 약 500MB인 v4 수치 ZIP을 코드 저장소에 커밋하면 안 된다. 큰 파일은 Release 첨부로 제공한다. [GitHub 공식 파일 크기 안내](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

전체 전달 ZIP은 저자 전달·보관용이다. 그것을 GitHub 코드 저장소의 단일 파일로 올리는 방식이 아니다. 별도로 제공된 `CAMV-Eval_GitHub_Repository_v8.zip`에는 작은 Git 트리만 들어 있다.

## 3. 공개 후 확인

실제로 공개된 저장소와 Release에서 내려받은 복사본으로 실행한다.

```powershell
python -m pip install -r requirements.txt
python fetch_assets.py --repository 실제소유자/실제저장소 --tag v8-repro-1 --output ../release-assets
python reproduce.py --mode all --assets-dir ../release-assets --output ../camv-public-check
```

이번에는 외부 공개 주소가 없으므로, 다운로드 명령의 온라인 실행은 검증하지 않았다. 로컬로 준비한 동일 ZIP들의 해시·추출·전체 수치 재현은 검증했다. 실제 저장소 주소가 정해지면 원고의 Data and Code Availability에 그 주소를 넣는다. DOI를 추가 발급하지 않았다면 DOI를 있다고 쓰지 않는다.

저자 소유 코드에는 확인된 MIT 라이선스가 적용된다. 외부 데이터·모델 및 수치 자료의 범위는 [LICENSE_SCOPE.md](../LICENSE_SCOPE.md)에 구분했다. 공개 패키지가 논문의 윤리·CRediT 선언을 대신하지는 않는다.
