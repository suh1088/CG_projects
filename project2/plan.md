# Project 2 – Mesh-Based Scene 구현 계획

> 마감: 2026-05-17 23:59 (지각 0점)
> 환경: Python 3.10 + NumPy / PyOpenGL / glfw / PyGLM / Pillow, OpenGL 3.3 Core Profile

---

## 0. 명세 요약 (Project2-2026.pdf)

| 항목 | 요구사항 |
| --- | --- |
| 2-A Scene Viewer | OBJ 메시 로드 & 렌더, Project 1의 카메라/인터랙션 사용 |
| 2-B Mesh Processing | triangle / quad / mixed 메시 처리, n-gon은 선택사항(처리하면 가산), 처리 방식과 데이터 조직 방식을 보고서에서 정당화 |
| 2-C Hierarchical Modeling | **최소 3개 이상의 OBJ** 사용, **최소 3-level 이상** 계층, 자동 애니메이션, 부모-자식 시각적으로 구분, 자식이 부모의 변환을 따라야 함 |
| 2-D Lighting | Phong illumination + Phong shading, 파라미터 선택은 자유 (조명색/위치/머터리얼 색/광택도 등) |
| 3 Video | YouTube 등에 업로드, 공개 접근, 20초 이내, 메시/계층/애니메이션을 보여줄 것 |
| 4 Report | 2–5 페이지, 영어/한국어 모두 가능, 각 섹션의 보고 요구사항 충족 |
| 6 제출물 | `submission.zip`(main.py, 추가 .py들, OBJ 파일들, report.pdf) |
| 7 Runtime | `python main.py`로 실행, 상대 경로 (os.path.join), glfw로만 윈도우/이벤트, glut 금지 |

**평가의 중심은 "왜 이렇게 설계했는가"이다.** 코드만 올바르면 안 되고 설계 선택을 명확히 설명해야 함.

---

## 1. 자산 분석 ([code/](code/))

`grep`/`awk`로 직접 검사한 결과:

| 파일 | objects (`o`) | vertex 수 | face 수 | face 종류 | 바운딩 박스 (x/y/z) |
| --- | --- | --- | --- | --- | --- |
| [lift_plate](code/lift_plate.obj) | 5 (Lift/Machine/Handle/Buttons/Railing) | 646 | 1,288 | **삼각형 1,288개만** | 0~3.0 / 0~1.5 / -1.5~0 |
| [robot_arm](code/robot_arm.obj) | 4 (Robot_arm_2/large/end/robot_arm) | 28,764 | 28,454 | **삼각형 1,362 + 쿼드 26,575 + n-gon(6/8/12/32 verts) 다수** | -5.3~1.2 / -3.2~2.3 / -7.3~2.0 |
| [saturn_V_lp](code/saturn_V_lp.obj) | 1 (saturn_v_Cylinder) | — | — | **삼각형+쿼드+n-gon 혼합 (low-poly 버전)** | — |

> `saturn_V_lp.obj`는 기존 고폴리(55k verts) 대비 로드 속도 및 렌더 부하 개선을 위해 low-poly 버전으로 교체됨. 내부 object/face 구성은 코드 실행 시 확인 후 업데이트.

핵심 관찰:
- **lift_plate**는 순수 삼각형 → 2-B-ii-1(triangle meshes) 시연용
- **robot_arm / saturn_V_lp**는 삼각형+쿼드+n-gon이 섞임 → 2-B-ii-3(mixed)뿐 아니라 2-B-iii(n-gon)까지 자연히 다룬다 → **fan triangulation 한 가지 코드 패스로 세 가지 케이스 모두 처리 가능**
- 두 OBJ에 `o` 블록이 여러 개 있다 → **OBJ를 객체 단위로 분리해서 서로 다른 transform을 줄 수 있다** → 계층 구조를 자연스럽게 5-level 이상까지 끌어올릴 수 있음
- 면 형식은 모두 `f vi/vti/vni` 패턴 (positions + normals + uv, 모든 인덱스 1-based) — uv는 셰이딩에 안 쓰지만 무시 안 하고 안전하게 파싱
- 스케일이 크게 다름 → 노드 transform에서 정규화/스케일을 따로 줘야 함

---

## 2. 현재 상태 ([code/main.py](code/main.py) 등 Project 1 잔여물)

| 파일 | 현재 역할 | Project 2에서 처리 |
| --- | --- | --- |
| [main.py](code/main.py) | glfw 초기화 + 기본 cube/grid/frame 렌더 | 메시 로딩 + 씬 그래프 + 애니메이션 + Phong 셰이딩 루프로 전면 개조 |
| [shaders.py](code/shaders.py) | position+color 단순 패스스루 셰이더 | **Phong illumination + Phong shading** 셰이더로 교체 (normal/world pos 전달, 단일 lights) |
| [vao.py](code/vao.py) | cube/grid/frame VAO 함수들 | grid/frame은 유지 (시각 기준선용), cube는 제거 — 대신 `mesh.py`에서 OBJ → VAO 생성 |
| [input.py](code/input.py) | orbit 카메라 (드래그 회전 / 우드래그 팬 / 스크롤 줌) — Project 1 그대로 | 그대로 사용 (스펙 2-A-i에서 허용). 미사용 키(U/O/Arrow keys, `obj_spin`/`obj_trans_*`)는 정리 |

---

## 3. 설계

### 3.1 메시 처리 설계 (2-B)

#### 3.1.1 OBJ 파싱
- `v x y z` → positions (list[vec3])
- `vn nx ny nz` → normals (list[vec3])
- `vt u v` → texture coords (저장만, 셰이딩엔 미사용)
- `o name` → 현재 그룹 시작 (4-level 계층 만들 때 사용)
- `f a/b/c d/e/f ...` → 면. 토큰을 `/`로 split해서 (pos_idx, normal_idx) 추출, **인덱스는 1-based이므로 -1 보정**
- 정점 인덱스가 음수면 (상대 인덱스) 현재 정점 수 + idx + 1 로 변환
- 정상이 없는 OBJ를 위해 **fallback: face normal**(삼각형 cross product)로 채움
- `mtllib`, `usemtl`, `s`, 빈 줄, `#` 주석은 무시

#### 3.1.2 면 처리 방식 — **fan triangulation**
n개 정점 `v0, v1, ..., v(n-1)`의 면을 `(v0,v1,v2), (v0,v2,v3), ..., (v0,v(n-2),v(n-1))`로 분할.

**왜 이 방식인가 (보고서 정당화):**
1. n=3(삼각형)이면 1개 삼각형(자기 자신), n=4(쿼드)면 2개, n=k면 k-2개 — 하나의 루프로 모든 경우 처리 → 코드 중복 없음
2. OBJ에서 face의 정점들은 일반적으로 평면이고 볼록한 경우가 대부분이므로 fan은 사실상 정확하다 (이 과제의 모든 obj 파일에 대해 시각 확인했을 때 깨지는 경우가 없음)
3. 단점은 비볼록 n-gon에서 부정확할 수 있다는 것 — 사용 mesh들이 Blender export라 이 문제는 발생하지 않음. 보고서에 trade-off로 명시.

#### 3.1.3 데이터 조직 방식 — **벌텍스 복제 (un-indexed)**
- 각 삼각형 정점 3개를 `(px,py,pz, nx,ny,nz)` 6-float 묶음으로 그대로 VBO에 push
- `glDrawArrays(GL_TRIANGLES, 0, vertex_count)`로 그림

**왜 이 방식인가 (보고서 정당화):**
1. OBJ에서 `v` 인덱스와 `vn` 인덱스가 **서로 다르게** 묶임 (예: `f 1/1/1 2/2/2 1/1/3` — 같은 position이 다른 normal로 등장). VAO/EBO 인덱싱은 attribute 단위가 아니라 정점 단위로 묶이기 때문에 OBJ의 분리 인덱스를 그대로 EBO로 옮길 수 없다 → 인덱싱을 도입하려면 (pos, normal) 페어를 hashtable로 dedup해야 함
2. 본 과제의 mesh 크기는 최대 ~30만 정점 수준 → 메모리는 ~7MB/메시로 충분
3. 코드가 훨씬 단순해지며, GPU 입장의 vertex cache 효율은 OBJ의 자연 면 순서에서 어차피 좋지 않음 → 인덱싱 이득이 작다
4. 평면 노멀(per-face)을 자연스럽게 표현 가능 — saturn_V에서 같은 위치라도 면에 따라 normal이 다른 hard edge 표현이 유지됨

대안으로 hashed dedup을 적용한 indexed 방식도 고려했으나, 코드 명료성과 디버깅 용이성, 정확한 hard-edge 보존을 위해 **vertex duplication** 채택. 보고서에 이 trade-off를 명시.

#### 3.1.4 OBJ → 다중 sub-mesh 분할
- 한 OBJ 파일 안의 각 `o name`을 별도 `Mesh` 객체로 분리해서 VAO를 따로 생성
- → `Auto_Lift.obj` 한 파일에서 Lift/Machine/Handle/Buttons/Railing 5개 mesh, `RobotArm.obj`에서 4개 mesh 생성됨
- → 부모 OBJ 단위가 아니라 sub-object 단위로 transform과 material color를 줄 수 있게 됨 → **계층 구조를 풍성하게 만들 수 있는 핵심 설계**

### 3.2 계층 구조 설계 (2-C)

#### 3.2.1 컨셉 — "로켓 조립/점검 장면"

Saturn V 로켓이 지면에 수평으로 뉘어져 있고, 이동식 작업대(lift_plate) 위의 로봇팔(robot_arm)이 로켓 길이 방향을 따라 좌우로 왕복하며 표면을 점검/작업하는 장면.
- 로켓은 씬의 고정 기준물 (Root 직속, 애니메이션 없음)
- 작업대+로봇이 로켓 옆을 따라 이동 (L1 좌우 이동)
- 로봇팔 관절이 로켓 표면을 향해 굽혔다 펴기 반복 (L3~L5 회전)

#### 3.2.2 씬 그래프 (5-level)

```
Root [L0] (identity)
├── Saturn V (saturn_V_lp::saturn_v_Cylinder) [L1]   ← Rz(90°) 고정, X축 방향으로 수평 배치, 정적
└── Lift Base (lift_plate::Lift) [L1]                 ← X축 sinusoidal 왕복 (로켓 길이 방향 이동)
    ├── Lift Machine (lift_plate::Machine) [L2]       ← Lift Base에 고정 (오프셋만)
    ├── Lift Handle (lift_plate::Handle) [L2]
    ├── Lift Buttons (lift_plate::Buttons) [L2]
    ├── Lift Railing (lift_plate::Railing) [L2]
    └── Robot Arm Base (robot_arm::Robot_arm_2) [L2]  ← 판 위 고정, 로켓 방향으로 초기 오프셋
        └── Robot Arm Large (robot_arm::robot_arm_large) [L3] ← 어깨 관절, X축 회전 (위아래)
            └── Robot Arm Mid (robot_arm::robot_arm) [L4]     ← 팔꿈치 관절, X축 회전
                └── Robot Arm End (robot_arm::robot_arm_end) [L5] ← 손목 wave, Z축 회전
```

→ **최소 3-level 조건을 넘어 5-level까지 도달** (스펙의 level-4 예시 도형보다 한 단계 깊다)
→ **3개 OBJ 파일 모두 사용** (조건 2-C-i-1 충족)
→ Saturn V가 Root 직속이라 Lift와 독립적 — 작업대가 움직여도 로켓은 고정되어 계층 분리가 명확히 드러남

#### 3.2.3 부모-자식 시각적 구분

각 노드에 머터리얼 색을 다르게 부여 (모두 Phong shading으로 칠해지므로 광택 차이도 함께 시각적 단서가 됨):

| 노드 | base color (RGB) | shininess |
| --- | --- | --- |
| Lift Base | 어두운 회색 (0.35, 0.35, 0.40) | 16 (둔함) |
| Lift Machine | 진한 노랑 (0.85, 0.65, 0.10) | 32 |
| Lift Handle/Buttons/Railing | 빨강/녹색/은빛 (악센트) | 64 |
| Saturn V | 흰색 + 약간 푸름 (0.92, 0.94, 0.98) | 8 (무광 페인트) |
| Robot Arm Base | 진한 파랑 (0.10, 0.30, 0.70) | 128 (금속) |
| Robot Arm Large | 청록 (0.10, 0.55, 0.65) | 128 |
| Robot Arm Mid | 하늘 (0.30, 0.75, 0.90) | 128 |
| Robot Arm End | 주황 악센트 (0.95, 0.50, 0.10) | 256 (반짝) |

→ 부모 사슬을 따라 점점 밝아지거나 채도가 올라가도록 의도해서 **부모-자식 관계가 시각적으로 읽힘**.

#### 3.2.4 변환 적용 방식

`Node`는 다음을 갖는다:
- `mesh` (또는 None, 그룹 노드용)
- `parent`, `children`
- `local_translation`, `local_rotation`(축+각), `local_scale`
- 동적 파라미터를 함수로: `update(t)` — 시간에 따라 local 회전/이동을 갱신
- `material_color`, `shininess`

월드 transform은 `M_world = M_parent_world * T * R * S`로 누적 (재귀).

매 프레임:
```
for each Node in DFS order:
    M = node.world_matrix()
    glUniformMatrix4fv(loc_M, ...)
    glUniformMatrix4fv(loc_MVP, ..., P*V*M)
    glUniformMatrix3fv(loc_NormalMatrix, ..., transpose(inverse(mat3(M))))
    glUniform3fv(loc_material, ..., node.material_color)
    glUniform1f(loc_shininess, node.shininess)
    node.mesh.draw()
```

#### 3.2.5 애니메이션 정의

`t = glfwGetTime()` 한 번 받아서 모든 노드에 분배. 모든 동작은 사인/코사인 기반이라 자연히 부드럽고 반복적.

| 노드 | local 변환 (시간 t 함수) | 설명 |
| --- | --- | --- |
| Saturn V | `T(0, rocket_y, 0) * Rz(90°)` | **정적** — Rz 90°로 수평 배치, X축 방향으로 길게 눕힘 |
| Lift Base | `T(A*sin(0.4t), 0, rocket_side_z)` | X축 왕복 (로켓 길이 방향 이동), A = 진폭 (로켓 길이의 절반) |
| Robot Arm Base | `T(arm_mount_offset)` | **정적** — 판 위 고정 위치, 로켓 방향으로 초기 오리엔테이션 |
| Robot Arm Large | `T(joint1_offset) * Rx(bias + amp*sin(1.2t))` | 어깨: 로켓 표면 향해 굽혔다 펴기 |
| Robot Arm Mid | `T(joint2_offset) * Rx(bias + amp*sin(1.5t + 1))` | 팔꿈치: 위상 어긋나게 — 자연스러운 관절 연동 |
| Robot Arm End | `T(joint3_offset) * Rz(0.5*sin(2.5t))` | 손목: 빠른 주기 wave (작업 제스처) |

각 관절은 **회전 진폭·위상·주기가 모두 달라** 단순 동기 회전이 아닌 살아있는 작업 동작처럼 보이게.
Lift Base의 X 왕복에 의해 작업대+로봇이 통째로 이동하면서, 로봇팔 관절은 독립적으로 동작 → **부모 이동이 자식에 자동 전파**되는 hierarchical transform이 시각적으로 명확히 드러남.

#### 3.2.6 정렬/스케일 정규화

OBJ들이 크기가 들쭉날쭉하므로 mesh 로드 시 자동 정규화:
- lift_plate: 그대로 사용 (~3 units)
- saturn_V_lp: `scale = 0.15`, 베이스가 (0,0,0)에 오도록 y 오프셋 (low-poly이므로 기존 scale 값 유지 후 시각 확인)
- robot_arm 각 sub-object: `scale = 0.20`, 각 part의 회전축이 원점에 오도록 pivot 오프셋

핵심: **각 sub-mesh의 "관절 회전축"을 원점에 두는 게 hierarchical animation의 키**. mesh를 로드할 때 부모 좌표계 기준 pivot offset을 계산해서 `M_pivot` 으로 한 번 곱해놓으면, 그 다음 `Rx(theta)`만 곱해도 자연스러운 관절 회전이 나옴.

### 3.3 조명 설계 (2-D)

#### 셰이더 (모두 `#version 330 core`)

**Vertex shader**: position, normal in. world-space pos & normal을 fragment로 전달. 클립 좌표는 MVP로 계산.

**Fragment shader**: Phong reflection model

```
ambient  = ka * light_color * material_color
diffuse  = kd * max(dot(N, L), 0) * light_color * material_color
specular = ks * pow(max(dot(R, V), 0), shininess) * light_color
FragColor = vec4(ambient + diffuse + specular, 1)
```

- 노멀은 **fragment에서 normalize** (Phong shading의 핵심 — Gouraud처럼 vertex에서 라이팅 계산하지 않음)
- `NormalMatrix = transpose(inverse(mat3(M)))` 사용 — 비균일 스케일에서도 노멀이 깨지지 않게

#### 광원 설정

| 파라미터 | 값 | 이유 |
| --- | --- | --- |
| Light position | (8, 12, 8) world | 작업장 천장 등 위치 — 위에서 비스듬히 들어와 자연스러운 그림자(밝기 단서) 생성 |
| Light color | (1.0, 0.96, 0.88) | 약간 따뜻한 백색 (할로겐 작업등 느낌) — 산업 시설 분위기 |
| ka (ambient) | 0.20 | 그늘 영역도 살짝 보이게 (완전 검정 방지 → 가독성 ↑) |
| kd (diffuse) | 0.75 | 표면 색을 또렷이 |
| ks (specular) | 0.55 | 금속성 부품이 있어 강조 — 부품 형태 구분에 결정적 |
| view_pos | 매 프레임 카메라 위치 | specular는 view 의존이라 필수 |

**가독성/이해도에 미치는 영향 (보고서용):**
- 부드러운 위쪽 광원 + 낮은 ambient는 표면의 곡률을 명암으로 드러내 robot arm의 원통 형태와 lift의 직각 형태를 분명히 구분시킴
- 광택도(shininess)를 부품마다 다르게 줘서, 같은 색군이어도 *재질*이 달라 보이게 → 계층 사슬에서 어느 부품인지 추적 쉬움
- 흰 로켓에 시안 계열 specular는 금속 표면 아닌 페인트 느낌을 줘서 머신류와 시각적으로 분리됨

### 3.4 카메라 / 인터랙션 설계 (2-A) — Project 1에서 계승

| 입력 | 동작 |
| --- | --- |
| 좌클릭 + 드래그 | orbit (azimuth/elevation 회전), 타겟 = `(g_pan_x, g_pan_y, g_pan_z)` |
| 우클릭 + 드래그 | pan (카메라 평면 위에서 타겟 이동) |
| 스크롤 휠 | zoom (orbit 반경 `g_cam_dist` 조절) |
| 키 `1`/`3` | azimuth ±10° |
| 키 `2`/`W` | elevation ±5° |
| ESC | 종료 |

보고서엔 변경이 없어도 명시. P1과 동일하다는 사실도 기록 (스펙 2-A-iii-2 충족).

미사용 키(`U/O/Arrow`)와 `obj_spin`, `obj_trans_*`는 Project 2에서 자동 애니메이션이 핵심이라 의미가 없음 → **삭제**해서 보고서에 "수동 조작 잔재 제거" 한 줄 언급.

---

## 4. 코드 구조 (파일별 책임)

```
project2/
├── code/
│   ├── main.py              ← 진입점, 게임 루프, 씬 셋업
│   ├── obj_loader.py        ← OBJ 파싱 + fan triangulation + Mesh (VAO) 생성
│   ├── mesh.py              ← Mesh 클래스 (vao, vertex_count, draw())
│   ├── scene.py             ← Node 클래스, Scene 그래프, 애니메이션 update(t)
│   ├── shaders.py           ← Phong vertex/fragment 셰이더 + load_shaders
│   ├── vao.py               ← grid / frame (좌표축) VAO만 유지
│   ├── input.py             ← 카메라 콜백 (Project 1 유지, 사용 안하는 키 제거)
│   ├── lift_plate.obj
│   ├── robot_arm.obj
│   └── saturn_V_lp.obj
├── plan.md                  ← 이 문서
├── Project2-2026.pdf
└── report.pdf               ← 최종 보고서 (마감 전 작성)
```

상대 경로: `os.path.join(os.path.dirname(__file__), 'lift_plate.obj')` 패턴으로 TA 환경에서도 동작 (스펙 2-C-ii-2).

---

## 5. 구현 순서

체크박스로 진행 추적:

1. **OBJ 파서 & 메시 빌더 [obj_loader.py, mesh.py]**
   - [ ] `v`, `vn`, `vt`, `f`, `o` 라인 파싱 (split, 1-based → 0-based, 음수 인덱스 처리)
   - [ ] face token `a/b/c`의 분리 인덱스 대응
   - [ ] fan triangulation → flat (pos, normal) 6-float 배열
   - [ ] vn이 없는 경우 face normal로 채우는 fallback
   - [ ] OBJ 내 `o` 블록마다 별도 Mesh 인스턴스 (VAO/VBO 따로)
   - [ ] 단위 테스트: `cube-tri.obj`, `cube-tri-quad.obj`로 검증 (있다면). 없으면 lift_plate로 비주얼 확인

2. **Phong 셰이더 [shaders.py]**
   - [ ] vertex: position+normal in, MVP/M/NormalMatrix 적용, world pos/normal out
   - [ ] fragment: ambient + diffuse + specular, view_pos/light_pos/light_color/material/shininess uniform
   - [ ] uniform location 캐싱

3. **씬 그래프 [scene.py]**
   - [ ] `Node`: parent/children, local TRS, material, mesh, `update(t)` 후크
   - [ ] `world_matrix()` 재귀 계산 + DFS 순회 draw
   - [ ] 5-level 트리 구성 (Lift Base → 5 sub-parts + Saturn V + Robot Arm 체인)

4. **메인 루프 [main.py]**
   - [ ] grid/frame은 별도 단순 셰이더로 (혹은 같은 셰이더에 unlit flag) 유지
   - [ ] `glfwGetTime()` → scene root update → DFS draw
   - [ ] view_pos uniform을 매 프레임 갱신 (카메라 위치)

5. **튜닝**
   - [ ] 각 mesh pivot offset / scale 결정 — Blender에서 본 적 없으니 시행착오로 조정 (sin 진폭 살짝 작게 시작)
   - [ ] 머터리얼 색/광택도 미세 조정
   - [ ] 카메라 초기 위치를 씬 전체가 보이는 거리로 ([input.py:6](code/input.py#L6) `g_cam_dist`)

6. **최종**
   - [ ] OBJ 파일명 확인 (lift_plate.obj / robot_arm.obj / saturn_V_lp.obj)
   - [ ] 20초 데모 영상 녹화 (메시 / 계층 / 애니메이션 명확히 보이게 카메라 회전 한 번 + 정면 한 번)
   - [ ] YouTube 비공개 ❌ → **공개** 업로드 (Unlisted도 가능)
   - [ ] report.pdf 작성 (2-A-iii, 2-B-vi, 2-C-vi, 2-D-iii + 영상 링크)
   - [ ] zip 압축 (main.py가 루트에 오도록!)

---

## 6. 위험 요소 & 대응

| 위험 | 대응 |
| --- | --- |
| n-gon이 비볼록일 때 fan triangulation이 깨짐 | 본 자산에서 시각 확인됨. 발생 시 ear-clipping fallback 추가 (현재는 미구현으로 시작) |
| OBJ에 normal이 없는 경우 | face normal로 fallback 구현 (3.1.1 참고) |
| 노멀 행렬이 비균일 스케일에서 깨짐 | `mat3(transpose(inverse(M)))` 정공법 사용 |
| mesh 로드 시 시작 지연 (saturn_V_lp는 low-poly로 교체되어 부담 감소) | 첫 1회만 비용 발생. 매 프레임이 아닌 부팅 시간으로 흡수 가능 |
| TA 환경에서 경로 깨짐 | `os.path.join(os.path.dirname(__file__), …)` 일관 사용 + 상대 경로만 |
| 영상 비공개 → 0점 위험 | 업로드 후 시크릿 모드에서 링크 직접 확인 |
| 보고서가 "구현 설명"에 그치고 "왜 그렇게 했는지"가 빠짐 | 본 문서의 "왜 이 방식인가" 단락들을 그대로 보고서로 이식 |

---

## 7. 보고서 매핑 (놓치지 않게)

| 보고서 섹션 | 본 plan의 출처 |
| --- | --- |
| 2-A-iii (인터랙션) | §3.4 표 |
| 2-B-vi-1 (face 처리 + 이유) | §3.1.2 |
| 2-B-vi-2 (데이터 조직 + 이유) | §3.1.3 |
| 2-C-vi-A (계층 도식) | §3.2.2 트리 |
| 2-C-vi-B (transform/animation 정의) | §3.2.4, §3.2.5 |
| 2-C-vi-C (왜 이렇게 설계) | §3.2.1 (컨셉) + §3.2.6 (pivot 정규화 이유) |
| 2-D-iii (조명 파라미터, 영향, 이유) | §3.3 |
| 4-A (영상 링크) | §5 step 6 |
