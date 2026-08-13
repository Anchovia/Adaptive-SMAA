# San Miguel 2.1 외부 장면 검증 결과

이 파일은 원본 장면을 Git에 복제하지 않고 출처, 해시와 저폴리 구성만 기록한다.

## 출처 및 사용 조건

- 배포 페이지: https://casual-effects.com/data
- 다운로드 URL: https://casual-effects.com/g3d/data10/research/model/San_Miguel/San_Miguel.zip
- 원 저작자: Guillermo M. Leal Llaguno
- 2017 개선: Morgan McGuire, Guedis Cardenas, Michael Mara, Nicholas Hull
- 원본 license.txt 조건: free for research and educational use with attribution
- ZIP SHA-256: `85874077735808150e679b3c71d70a37a270cb8833f4911325aa1099da3f7d4a`
- 저폴리 OBJ SHA-256: `7142519da39589857d7dfcd3143a7b41bd444279f65dd5177c3adfad29a1ecc9`

## 저폴리 실시간 장면 구성

- OBJ 크기: 628,033,664 bytes
- 정점: 3,738,829
- texture coordinates: 844,670
- 법선: 4,517,249
- 삼각형: 5,617,451
- 오브젝트: 1,130
- 사용 재질: 281
- AABB extent: (69.049, 14.869, 26.980)

## 재질과 텍스처

- MTL 재질: 281
- diffuse map: 265
- bump/normal 계열: 55
- specular map: 2
- ZIP PNG: 323
- 실제 alpha 포함 참조 texture: 79
- alpha-test로 표시한 재질: 97
- 누락 참조: 0

## 연구상 분류

- 텍스처와 실제 건축·가구·식생을 포함하는 현실적 품질 장면이다.
- alpha texture 식생과 얇은 난간·가구는 subpixel geometry 복구 평가에 사용한다.
- Power Plant는 배관 geometry stress, San Miguel은 textured real-scene quality로 구분한다.
- 원본 ZIP, OBJ와 PNG는 D 드라이브에만 두며 Git에는 포함하지 않는다.
