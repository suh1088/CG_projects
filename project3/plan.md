# Project 3 구현 계획 — BVH Motion Viewer

> 마감: **2026-06-07 23:59** (지각 = 0점)
> 제출: `submission.zip` (= `main.py` + 기타 `.py` + `report.pdf` + 사용한 `.bvh`/에셋)
> 실행: `python main.py`
> 환경: Python 3.10 / NumPy, PyOpenGL, glfw, PyGLM, Pillow **만** 사용 / OpenGL 3.3 Core / 이벤트·윈도우는 **glfw만** (glut 금지)

---

## 0-A. 이번 과제 시나리오 (확정)

1. **무대(stage)** 를 `obj_loader` 로 먼저 로드해 바닥/배경 메시로 깐다.
2. 그 무대 위에서 **`walk` → `dance` → `walk`** 순서로 모션을 **이어서** 재생한다.
3. 동작 경계(walk끝→dance시작, dance끝→walk시작)는 **이전 동작의 마지막 자세에서 다음 동작의 시작 자세로 보간(interpolate)** 한다.
   - **위치 순간이동 금지**: 다음 클립을 이전 클립의 끝 위치·바라보는 방향(yaw)에 맞춰 정렬한 뒤 재생.
   - **자세 급변 금지**: 경계에 짧은 전환 구간(≈0.3~0.5초)을 끼워 관절 회전을 부드럽게 보간(slerp).

> `walk.bvh` 와 `dance.bvh` 는 HIERARCHY·OFFSET·채널·FrameTime(120fps)이 **완전히 동일한 동일 골격**임을 확인했다(diff 일치). 따라서 한 개의 Joint 트리를 공유하고, 프레임 채널 배열만 바꿔 끼우면 되며, 관절끼리 1:1 대응되므로 **포즈 블렌딩이 성립**한다.

---

## 0-B. 전략 — P1/P2 코드 최대 재활용

이번 과제는 "처음부터"가 아니라 **Project 1·2 뷰어의 확장**이다. 기존 모듈을 거의 그대로 가져오고, OBJ 대신 BVH를 다루는 부분만 새로 만든다.

| 기존 파일 | 재활용 여부 | Project 3에서의 역할 |
|---|---|---|
| `input.py` | **거의 그대로** | 카메라 orbit/pan/zoom. 여기에 재생 제어 키(스페이스/방향키 등)만 추가 |
| `vao.py` | **그대로** | grid / world axis frame / pivot 렌더 |
| `obj_loader.py` | **그대로 사용** | **무대(stage) `.obj` 로드** (`load_obj`+`make_vao`+`Node`). 또한 `Node` 의 `update_tree_global_transform` 패턴을 BVH 골격에 그대로 적용 |
| `shaders.py` | **그대로** | unlit(라인/그리드) + Phong(무대·관절·뼈대 메시) 셰이더 2종 |
| `main.py` | **골격 재활용** | glfw 초기화 → 셰이더 로드 → 렌더 루프 구조 동일, 내용만 (무대 + BVH 시퀀스)로 교체 |

> P2의 `Node`는 부모×자식 글로벌 변환 누적 트리다. BVH 골격(joint tree)도 정확히 같은 구조이므로 이 패턴을 그대로 가져온다. 무대는 별도 루트 `Node` 하나로 둔다.

---

## 1. 파일 구성 (제출 기준)

```
submission.zip
├─ main.py            # 진입점: glfw/GL 초기화, 무대+골격 렌더 루프, 키 바인딩
├─ bvh_loader.py      # ★신규: BVH 파서 + Joint 트리 + 프레임→Pose 변환
├─ motion_sequence.py # ★신규: 여러 클립 정렬(align)+전환 보간(blend)+통합 타임라인
├─ skeleton_render.py # ★신규: 관절(구)·뼈(실린더) 지오메트리 VAO + 포즈 적용 렌더
├─ obj_loader.py      # 무대 OBJ 로드 (P2 그대로)
├─ input.py           # 카메라 + 재생 제어 콜백 (P1/P2 확장)
├─ vao.py             # grid/frame/pivot (P1 그대로)
├─ shaders.py         # unlit + Phong (P2 그대로)
├─ report.pdf
├─ stage.obj          # 무대 메시 (또는 assets/ 하위)
└─ bvh/               # 사용한 BVH 파일들 (상대경로, os.path.join)
   ├─ walk.bvh
   └─ dance.bvh
```

경로는 반드시 `os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bvh', 'walk.bvh')` 형태로 — 플랫폼 독립 + 상대경로 (요구사항 5-C). 무대 OBJ·BVH 모두 zip에 포함.

---

## 2. 무대(Stage) 로드 — `obj_loader` 재활용

P2의 `load_obj` → `make_vao` → `Node` 파이프라인을 **그대로** 쓴다.

```
stage_groups = load_obj(os.path.join(CODE_DIR, 'stage.obj'))
stage_vao, stage_count = make_vao(sum(stage_groups.values(), []))   # 전 그룹 합쳐 단일 VAO
stage = Node(None, glm.mat4(), glm.vec3(0.55, 0.55, 0.60))          # 회색 바닥
stage.set_vao(stage_vao); stage.set_vertex_count(stage_count)
```

- **배치/스케일**: 무대 윗면이 `y=0` 평면이 되도록 `stage.set_transform(scale·translate)`. 골격 발이 무대 위에 서도록 §3.3 의 골격 수직 오프셋과 맞춘다.
- **렌더**: Phong 셰이더로 그린다(골격과 동일 머티리얼 경로). grid/axis 는 unlit 그대로.
- 무대는 정적이므로 매 프레임 transform 갱신 불필요(1회 설정).

---

## 3. BVH 파서 & 골격 (`bvh_loader.py`)

BVH 파일은 `HIERARCHY` 섹션과 `MOTION` 섹션으로 나뉜다. `str.split()`만으로 충분히 파싱 가능(과제 힌트 9-A).

### 3.1 HIERARCHY 파싱 → Joint 트리

각 줄을 토큰화하며 스택 기반으로 트리를 구성한다.
- `ROOT name` / `JOINT name` → 새 `Joint` 생성, 스택 top을 부모로 연결, 스택에 push
- `OFFSET x y z` → 현재 joint의 부모 기준 로컬 오프셋(`glm.vec3`)
- `CHANNELS n c1 c2 ...` → 채널 목록 저장. **회전 순서(rotation order)가 joint마다 다를 수 있으니 문자열 그대로 보관** (walk/dance: root=`XYZ pos, ZYX rot`, 그 외=`ZXY rot`)
- `End Site` → 말단(자식 없음, OFFSET만). 뼈 끝을 그리기 위해 leaf로 저장
- `{` → push, `}` → pop

```python
class Joint:
    name, parent, children[]
    offset            # glm.vec3, 부모 기준 로컬 위치
    channels[]        # ['Zrotation','Xrotation','Yrotation', ...]
    channel_index     # MOTION 한 프레임 배열에서 이 joint 채널 시작 인덱스
    global_transform  # 매 프레임 계산 (P2 update_tree_global_transform 동일 패턴)
```

### 3.2 MOTION 파싱
- `Frames: N`, `Frame Time: dt` (walk/dance 둘 다 0.00833 → 120fps)
- 이후 N줄을 `np.array` 로 `(N, total_channels)` 2D 배열로 저장

### 3.3 좌표 스케일 + 지면 정렬 (요구사항 2-A-1-A)
- BVH마다 단위가 달라 골격 크기가 제각각 → 골격 bounding box 높이로 목표 키(예 ~2.0 단위)에 맞춰 `scale` 자동 산출, OFFSET·루트 위치에 곱한다.
  - **시퀀스의 모든 클립은 같은 골격이므로 동일 scale 1개를 공유**(클립마다 다른 scale 쓰면 전환 시 크기 점프). walk/dance 동일 골격이라 자동으로 동일.
- **지면 정렬**: walk 전 구간에서 발(LeftToe/RightToe 등 말단)의 최저 월드 Y를 구해, 그 값이 무대 윗면 `y=0` 에 오도록 루트에 수직 오프셋을 더한다 → 발이 무대를 뚫거나 뜨지 않음.

### 3.4 프레임 → **Pose** 로 변환 (★전환 보간을 위한 핵심 추상화)

채널 배열을 그대로 쓰지 않고, **중립 표현 `Pose`** 로 변환해서 보관/블렌딩한다.

```python
class Pose:
    root_pos    # glm.vec3  (루트 translation 채널, scale 적용 후)
    rotations   # [glm.quat] * joint_count  (각 joint 로컬 회전, 채널 순서대로 곱한 결과를 quat 로)
```

- 각 joint 로컬 회전: 채널 **순서대로** `R = Rz*Rx*Ry …` (파일 순서 준수!) 로 만든 뒤 `glm.quat_cast` 로 쿼터니언화.
- 회전은 도(degree) → `glm.radians`.
- 클립 전체를 `poses: list[Pose]` 로 미리 변환해 두면, 렌더·정렬·블렌딩이 전부 동일 형식으로 처리된다.

### 3.5 Pose → global_transform (렌더용)

P2 트리 순회를 그대로 차용:
```
joint 로컬 변환 L = T(offset) * R(pose.rotations[i])      # 루트는 L = T(pose.root_pos) * R(rotations[0])
global_transform = parent.global_transform * L            # 루트는 L 그대로
```

---

## 4. 모션 시퀀스 + 전환 보간 (`motion_sequence.py`) ★이번 과제 핵심

`clips = [walk_poses, dance_poses, walk_poses]` 를 하나의 연속 타임라인으로 합친다.
동일 골격이므로 `Pose` 끼리 직접 정렬·보간이 가능하다.

### 4.1 위치·방향 정렬 (위치 순간이동 제거)

클립 `B` 를 이전(이미 정렬된) 클립 `A` 의 **마지막 Pose** 에 이어붙인다.

```
A_last  = A.poses[-1]              # 끝 자세
B_first = B.poses[0]               # 시작 자세 (raw)

# 1) yaw(=수평 진행방향) 차이만 보정  → A 의 진행방향을 그대로 이어감
yaw_A = heading_yaw(A_last.rotations[0])     # 루트 회전에서 Y축 성분(yaw) 추출
yaw_B = heading_yaw(B_first.rotations[0])
q_align = glm.angleAxis(yaw_A - yaw_B, (0,1,0))

# 2) B 전체 루트에 q_align 적용 + XZ 평행이동으로 시작점을 A 끝점에 맞춤
for p in B.poses:
    p.rotations[0] = q_align * p.rotations[0]
    p.root_pos     = q_align * (p.root_pos - B_first.root_pos) + A_last.root_pos
```
- **XZ(수평) + yaw 를 맞추는 것이 순간이동 제거의 핵심.** 수직 Y 와 잔여 자세 차이는 4.2 전환 구간이 흡수.
- 루트만 변환하므로 클립 내부 동작(걸음·춤)은 그대로 보존.

### 4.2 전환 구간 보간 (자세 급변 제거)

정렬된 `A` 와 `B` 사이에 **전환 프레임 T개**(예 0.4초 → 48프레임 @120fps) 를 새로 생성해 끼운다.
`k = 1..T`, `α = smoothstep(k/(T+1))` (ease-in/out):

```
trans_pose.root_pos       = lerp(A_last.root_pos, B_first.root_pos, α)
trans_pose.rotations[i]   = glm.slerp(A_last.rotations[i], B_first.rotations[i], α)   # 모든 joint
```
- **회전은 quaternion `slerp`** → 최단경로·짐벌락 없는 부드러운 보간 (Euler 선형보간 대비 안정적).
- B 가 4.1 로 정렬돼 있으므로 root_pos 보간은 거의 제자리(잔여 Y/미세차만 메움) → 미끄러짐 최소.

### 4.3 통합 타임라인

```
timeline_poses = walk + [trans(walk→dance)] + dance + [trans(dance→walk)] + walk
```
- `MotionSequence` 가 `poses` 단일 리스트 + 총 프레임 수를 보유.
- (선택) 마지막→처음도 정렬+전환을 넣어 **무한 루프**가 매끄럽게 돌게 할 수 있음.

### 4.4 시간 기반 재생 (요구사항 2-A-2)
```
elapsed = (now - start) * play_speed
frame   = int(elapsed / frame_time) % total_frames    # 자동 루프
skeleton.apply_pose(timeline_poses[frame])
```
- 구간 경계 표시(현재 walk/dance/transition 중 무엇인지)를 콘솔/HUD 로 디버그 출력하면 검증 편함.

---

## 5. 골격 렌더링 (`skeleton_render.py`, 요구사항 2-A-3)

- **관절(joint)**: 구(sphere) — 단위 sphere 정점 배열 1회 생성·재사용, joint마다 위치만 바꿔 그림
- **뼈(bone)**: 부모→자식 OFFSET 을 잇는 실린더/박스. 단위 실린더(+Y, 길이 1) VAO 1개를 `(길이 스케일)·(방향 회전)·(부모 위치 이동)` 으로 배치
- 모두 **P2 Phong 셰이더 재사용** → 무대와 동일 음영. grid/축/pivot 은 P1 unlit
- 단위 지오메트리(`make_sphere_vao`, `make_cylinder_vao`)는 position+normal 인터리브 → `obj_loader.make_vao` 와 동일 attrib 레이아웃(loc0 pos, loc1 normal)

---

## 6. 카메라 / 인터랙션 (요구사항 2-A-4, `input.py`)

**카메라 (P1/P2 그대로)**: 좌드래그 orbit / 우드래그 pan / 스크롤 zoom.

**재생 제어 (신규 — `key_callback` 추가)**:
- `Space`: 재생/일시정지
- `←` / `→`: 한 프레임 뒤로/앞으로 (스크럽)
- `[` `]`: 재생 속도 증감
- `R`: 처음으로 리셋

상태 전역변수는 P2 `input.py` 패턴 유지(`g_playing`, `g_play_speed`, `g_cur_frame`, `g_paused_time` 등).

---

## 7. 추가 응용 (요구사항 2-B — 여력 시)

**시퀀스+전환 보간 자체가 핵심 모션 응용**(2-B)이다. 보고서에 "왜·어떻게"를 적는다. 여력이 있으면 1개 추가:
- **모션 궤적 + 잔상(onion-skin)**: 루트/발의 프레임별 월드 위치를 `GL_LINE_STRIP` 으로 누적, 전환 구간이 매끄럽게 이어지는 걸 시각적으로 강조. 키 `T`.
- **follow-cam**: 카메라가 루트를 부드럽게 추적(`g_pan_*` 를 루트 위치로 lerp). 무대 위 이동을 보기 좋게.

---

## 8. main.py 렌더 루프 구조 (P1/P2 확장형)

```
glfwInit → window hints(3.3 core) → create window
콜백 4종 등록 (input.py)
prog_unlit, prog_phong = load_shaders(...)            # shaders.py 재사용
vao_grid/frame/pivot = vao.py                          # P1 재사용
stage = obj_loader 로 stage.obj 로드 → Node            # §2
skel  = parse_bvh(walk), parse_bvh(dance)              # §3, 동일 골격
seq   = MotionSequence([walk, dance, walk])            # §4 정렬+전환+타임라인
unit_sphere_vao, unit_cyl_vao = skeleton_render        # §5
loop:
   clear, P/V/VP 계산 (P1 카메라 수식 그대로)
   [unlit]  grid / axis / pivot
   [phong]  stage 그리기
   frame 계산(glfwGetTime, play 상태)
   skel.apply_pose(seq.poses[frame]) → 트리 global_transform 갱신
   [phong]  각 joint 구 + 각 bone 실린더 draw
   [응용]   궤적/잔상/follow-cam (토글 시)
   swap, poll
```

---

## 9. 보고서 (report.pdf, 2~5p, 한/영 자유)

템플릿 `Project3-report-template(kr).docx`. 포함 항목:
1. **뷰어 설계** (2-A-ii): 무대(OBJ) 구성 / 골격 표현(구+실린더+Phong) 이유 / 인터랙션 설계 이유
2. **모션 응용** (2-B-iii): **walk→dance→walk 시퀀스 + 위치·yaw 정렬 + slerp 전환 보간** 의 동작 방식·선택 이유(흥미점). 순간이동/자세급변을 어떻게 제거했는지 명시
3. **사용 BVH**: 데이터셋 출처명 + 동작 설명 (walk/dance 동일 골격임도 언급)
4. **영상 링크** (3-A): YouTube/Vimeo **공개** 링크

## 10. 영상 (요구사항 3)
- **20초 이하**, 공개. 시연: ① 무대 위 골격 모션 재생 ② 카메라/뷰어 조작 ③ **walk→dance→walk 전환이 매끄럽게 이어지는 장면**.

---

## 11. 작업 순서 (체크리스트)

- [ ] `project3/code/` 에 P1/P2 `input.py`,`vao.py`,`shaders.py`,`obj_loader.py` 정리(재활용 기반)
- [x] **무대 OBJ 로드** → `Node` 로 Phong 렌더, `y=0` 윗면에 배치 (거대 바닥판 제외)
- [x] `bvh_loader.py`: HIERARCHY 파서 → Joint 트리(이름·계층 콘솔 확인 완료)
- [x] MOTION 파서 + `(N,C)` 배열 + 프레임→`Pose`(quat) 변환
- [x] 한 Pose → `global_transform`(채널 순서 준수) — apply_pose 구현, 월드좌표 검증(높이 2.003)
- [x] 자동 스케일 완료 / 발 지면 정렬 오프셋 산출(−min Y=0.069) — 렌더 단계에서 적용 예정
- [x] 민트색 박스(직육면체) 뼈대 + Phong 렌더로 골격 시각 검증 (skeleton_render.py)
- [x] `motion_sequence.py`: ① 위치·yaw 정렬(순간이동 제거, 경계 XZ 점프 0.0000) ② slerp 전환 구간(48프레임) ③ 통합 타임라인(1838프레임)
- [x] `glfwGetTime` 기반 루프 재생(walk→dance→walk 자동 루프 + loop 전환)
- [ ] (선택) 관절 구(sphere) 추가 — 현재 뼈는 박스로 완료
- [x] 재생 제어 키(space 일시정지 / ←→ 스크럽 / [ ] 속도 / R 리셋) — input.py + dt 기반 재생
- [ ] (여력) 궤적/잔상 또는 follow-cam
- [ ] 상대경로 정리(무대·BVH zip 포함 확인)
- [ ] 보고서 작성, 영상 촬영·업로드·링크
- [ ] zip 패키징 후 깨끗한 폴더에서 `python main.py` 최종 실행 검증

## 12. 흔한 함정 (감점 방지)
- 회전 **채널 순서** 무시(파일 순서대로 곱해야 함) / degree→radian 변환 누락
- 전환 보간을 **Euler 선형보간**으로 해서 짐벌락·먼 길 회전 발생 → **quaternion slerp** 사용
- 클립마다 다른 스케일 적용 → 전환 시 크기 점프 (시퀀스 전체 단일 scale)
- 정렬 시 yaw·XZ 안 맞춰 **순간이동** 발생
- End Site 미처리로 말단 뼈 누락
- 절대경로/플랫폼 의존 경로 → `os.path.join` 필수, 무대·BVH zip 누락 금지
- 허용 외 모듈 / OpenGL 3.3 core·`#version 330 core` 누락 / 영상 비공개·링크 누락
