"""BVH 파서 + Joint 트리 + 프레임 → Pose 변환  (plan.md §3)

설계 요점
 - HIERARCHY 를 스택 기반으로 파싱해 P2 `Node` 와 동형의 Joint 트리 구성
 - 회전 채널 순서(rotation order)는 joint 마다 다를 수 있으므로 문자열 그대로
   보관하고, MOTION 적용 시 "파일에 적힌 순서대로" 곱한다. (흔한 버그 포인트)
 - 각 프레임을 채널 배열이 아니라 중립 표현 ``Pose`` (루트 위치 + joint 별
   로컬 회전 quaternion) 로 변환한다. → 이후 motion_sequence 에서 클립 정렬·
   slerp 전환 보간·렌더를 모두 동일 형식으로 처리하기 위함.
"""

import numpy as np
import glm


_AXIS = {'X': glm.vec3(1, 0, 0),
         'Y': glm.vec3(0, 1, 0),
         'Z': glm.vec3(0, 0, 1)}


# ── Joint ─────────────────────────────────────────────────────────────────

class Joint:
    """P2 Node 와 동형. 부모→자식 글로벌 변환 누적 트리의 노드."""
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.children = []
        self.offset = glm.vec3(0.0)      # 부모 기준 로컬 오프셋 (raw, scale 미적용)
        self.channels = []               # ['Zrotation','Xrotation','Yrotation', ...]
        self.channel_index = 0           # MOTION 한 행에서 이 joint 채널 시작 인덱스
        self.is_end_site = False
        self.global_transform = glm.mat4(1.0)
        if parent is not None:
            parent.children.append(self)


# ── Pose (중립 표현) ────────────────────────────────────────────────────────

class Pose:
    """한 프레임의 자세. 정렬/보간/렌더가 공유하는 표현.

    root_pos  : glm.vec3  — 루트 translation (scale 적용 후)
    rotations : list[glm.quat] — joints 와 같은 순서/길이. 각 joint 로컬 회전.
                (End Site 등 회전 채널 없는 joint 는 단위 quaternion)
    euler     : list[list[(axis_char, angle_deg)]] — joint 별 회전 채널의 오일러 각
                (채널 순서 그대로). 전환 구간의 오일러 보간에 사용. None 가능.
    """
    __slots__ = ('root_pos', 'rotations', 'euler')

    def __init__(self, root_pos, rotations, euler=None):
        self.root_pos = root_pos
        self.rotations = rotations
        self.euler = euler

    def copy(self):
        e = None if self.euler is None else [list(ch) for ch in self.euler]
        return Pose(glm.vec3(self.root_pos), [glm.quat(q) for q in self.rotations], e)


# ── BVH ─────────────────────────────────────────────────────────────────────

class BVH:
    def __init__(self, joints, root, frames, frame_time):
        self.joints = joints                 # DFS 순서 (End Site 포함) — 부모가 항상 먼저
        self.root = root
        self.frames = frames                 # np.ndarray (N, C)
        self.frame_time = frame_time
        self.num_frames = int(frames.shape[0]) if frames.size else 0
        self.scale = 1.0                     # 자동 스케일 계수 (auto_scale 로 설정)
        self.poses = []                      # list[Pose] — build_poses() 로 채움

    # 자동 스케일: rest pose(모든 회전 단위) 의 bounding-box 높이를 목표 키에 맞춤
    def auto_scale(self, target_height=2.0):
        ys = []
        world = {}
        for j in self.joints:
            p = j.offset if j.parent is None else world[j.parent] + j.offset
            world[j] = p
            ys.append(p.y)
        height = (max(ys) - min(ys)) if ys else 0.0
        self.scale = (target_height / height) if height > 1e-6 else 1.0
        return self.scale

    # 모든 프레임 → Pose 리스트
    def build_poses(self):
        self.poses = [self.frame_to_pose(self.frames[f]) for f in range(self.num_frames)]
        return self.poses

    # 한 프레임 행 → Pose
    def frame_to_pose(self, row):
        root_pos = glm.vec3(0.0)
        rotations = []
        euler = []
        for j in self.joints:
            q = glm.quat()                   # identity (w=1)
            erot = []                        # 이 joint 의 회전 채널 (axis, angle_deg)
            idx = j.channel_index
            for c in j.channels:
                v = float(row[idx]); idx += 1
                if c == 'Xposition':
                    if j is self.root: root_pos.x = v
                elif c == 'Yposition':
                    if j is self.root: root_pos.y = v
                elif c == 'Zposition':
                    if j is self.root: root_pos.z = v
                elif c == 'Xrotation':
                    q = q * glm.angleAxis(glm.radians(v), _AXIS['X']); erot.append(('X', v))
                elif c == 'Yrotation':
                    q = q * glm.angleAxis(glm.radians(v), _AXIS['Y']); erot.append(('Y', v))
                elif c == 'Zrotation':
                    q = q * glm.angleAxis(glm.radians(v), _AXIS['Z']); erot.append(('Z', v))
            rotations.append(q)
            euler.append(erot)
        root_pos = root_pos * self.scale
        return Pose(root_pos, rotations, euler)

    # Pose 적용 → 트리 global_transform 갱신 (P2 update_tree_global_transform 패턴)
    def apply_pose(self, pose):
        s = self.scale
        for k, j in enumerate(self.joints):
            R = glm.mat4_cast(pose.rotations[k])
            if j.parent is None:
                local = glm.translate(glm.mat4(1.0), pose.root_pos) * R
                j.global_transform = local
            else:
                local = glm.translate(glm.mat4(1.0), j.offset * s) * R
                j.global_transform = j.parent.global_transform * local


# ── 파서 ─────────────────────────────────────────────────────────────────────

def parse_bvh(path, target_height=2.0, build_poses=True):
    """BVH 파일 → BVH 객체. auto_scale 적용 후 (옵션) 전체 Pose 미리 변환."""
    with open(path, encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    joints = []
    root = None
    stack = []
    channel_cursor = 0
    i, n = 0, len(lines)

    # ── HIERARCHY ──
    while i < n:
        toks = lines[i].split()
        i += 1
        if not toks:
            continue
        key = toks[0]

        if key in ('ROOT', 'JOINT'):
            parent = stack[-1] if stack else None
            j = Joint(toks[1], parent)
            joints.append(j)
            if key == 'ROOT':
                root = j
            stack.append(j)
        elif key == 'End':                       # "End Site"
            parent = stack[-1]
            j = Joint(parent.name + '_End', parent)
            j.is_end_site = True
            joints.append(j)
            stack.append(j)
        elif key == 'OFFSET':
            stack[-1].offset = glm.vec3(float(toks[1]), float(toks[2]), float(toks[3]))
        elif key == 'CHANNELS':
            cur = stack[-1]
            cnt = int(toks[1])
            cur.channels = toks[2:2 + cnt]
            cur.channel_index = channel_cursor
            channel_cursor += cnt
        elif key == '}':
            stack.pop()
        elif key == 'MOTION':
            break
        # '{' 와 'HIERARCHY' 는 무시

    # ── MOTION 헤더 ──
    frame_time = 0.0
    while i < n:
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line.startswith('Frames:'):
            pass                                 # 개수는 데이터에서 직접 카운트
        elif line.startswith('Frame Time:'):
            frame_time = float(line.split(':', 1)[1])
            break

    # ── MOTION 데이터 ──
    data = []
    while i < n:
        s = lines[i].strip()
        i += 1
        if s:
            data.append([float(x) for x in s.split()])
    frames = np.array(data, dtype=np.float32) if data else np.zeros((0, channel_cursor), np.float32)

    bvh = BVH(joints, root, frames, frame_time)
    bvh.auto_scale(target_height)
    if build_poses:
        bvh.build_poses()
    return bvh


# ── 디버그용 트리 출력 ──────────────────────────────────────────────────────

def print_tree(joint, depth=0):
    ch = '' if joint.is_end_site else f"  [{','.join(c[0] for c in joint.channels)}]"
    print('  ' * depth + f"{joint.name}{ch}")
    for c in joint.children:
        print_tree(c, depth + 1)


if __name__ == '__main__':
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in ('walk.bvh', 'dance2.bvh'):
        path = os.path.join(here, fn)
        if not os.path.exists(path):
            print(f"(skip) {fn} 없음"); continue
        bvh = parse_bvh(path)
        joints = [j for j in bvh.joints if not j.is_end_site]
        print(f"\n===== {fn} =====")
        print(f"joints={len(joints)} (+End {len(bvh.joints)-len(joints)})  "
              f"frames={bvh.num_frames}  frame_time={bvh.frame_time:.6f}  "
              f"scale={bvh.scale:.4f}  poses={len(bvh.poses)}")
        print_tree(bvh.root)
