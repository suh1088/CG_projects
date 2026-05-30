"""모션 시퀀스 + 전환 보간 (plan.md §4)

여러 BVH 클립(동일 골격)을 하나의 연속 타임라인으로 잇는다.
 ⓪ 선행/후행 T자(캘리브레이션) 프레임 트리밍
      → 전환이 "다음 동작의 실제 시작 자세"로 향하게 한다. (T자로 빠지는 버그 해결)
 ① 위치 정렬       : 다음 클립을 이전 클립 끝의 XZ 위치에 맞춤 → 순간이동 제거
 ② 방향(yaw) 정렬  : 진행방향 연속. 단 **마지막 walk 는 처음 walk 와 같은 방향**.
 ③ 전환 보간       : t 를 0→1 로 선형 증가시키며 보간.
      root 위치는 성분 선형보간(lerp), 회전은 quaternion 구면 선형보간(slerp).
      (이징 없이 일정 속도 → 전환 양끝 "멈칫" 끊김 제거)
 ④ 통합 타임라인   : clip0 + trans + clip1 + trans + ... (+옵션 loop 전환)

같은 클립이 여러 번 등장하므로(walk→dance→walk) 원본 Pose 를 변형하지 않고
**복사본**에 정렬을 적용한다.
"""

import math
import glm

from bvh_loader import Pose


# ── 유틸 ─────────────────────────────────────────────────────────────────────

def _heading_yaw(q):
    """루트 회전 quaternion 에서 수평 진행방향(Y축 회전각, rad)을 추출."""
    d = q * glm.vec3(0.0, 0.0, 1.0)              # forward 를 회전
    return math.atan2(d.x, d.z)


def _slerp(qb, qc, t):
    """B → C 로 quaternion 구면 선형보간(slerp).

    최단경로를 위해 dot<0 이면 C 부호를 반전한 뒤 glm.slerp 로 보간한다.
    (구면상 등속 각보간 → 짐벌락·오일러 wrap 문제 없음)
    """
    if qb.w * qc.w + qb.x * qc.x + qb.y * qc.y + qb.z * qc.z < 0.0:
        qc = glm.quat(-qc.w, -qc.x, -qc.y, -qc.z)
    return glm.normalize(glm.slerp(qb, qc, t))


def _pose_activity(pose):
    """전 관절 로컬 회전의 identity 대비 총 회전각(deg). T자(rest)면 작다."""
    s = 0.0
    for q in pose.rotations:
        w = max(-1.0, min(1.0, abs(q.w)))
        s += math.degrees(2.0 * math.acos(w))
    return s


def _pose_velocity(pa, pb):
    """두 프레임 사이 전 관절 회전 변화량 합(deg/frame). T자 스냅 구간에서 크다."""
    s = 0.0
    for qa, qb in zip(pa.rotations, pb.rotations):
        dq = glm.inverse(qa) * qb
        s += math.degrees(2.0 * math.acos(max(-1.0, min(1.0, abs(dq.w)))))
    return s


def _trim_rest(poses, rest_ratio=0.5, vel_ratio=2.0):
    """선행/후행의 T자(rest) + 그 직후 "스냅 램프"(고속) 프레임을 잘라낸다.

    BVH 클립은 보통 frame0=T자 이후 몇 프레임에 걸쳐 본 자세로 급가속(정상의
    수 배 속도)한다. 활성도만으로 자르면 이 고속 램프가 클립 시작에 남아 전환
    직후 움찔거림을 만든다. → 활성도가 낮거나(rest) **각속도가 정상(중앙값)의
    vel_ratio 배를 넘는** 선행/후행 프레임을 함께 제거한다.
    """
    n = len(poses)
    if n < 4:
        return poses
    acts = [_pose_activity(p) for p in poses]
    vels = [0.0] + [_pose_velocity(poses[i - 1], poses[i]) for i in range(1, n)]
    a_th = rest_ratio * sorted(acts)[n // 2]
    v_th = vel_ratio * sorted(vels)[n // 2]

    lo = 0
    while lo < n - 1 and (acts[lo] < a_th or vels[lo] > v_th):
        lo += 1
    hi = n
    while hi - 1 > lo and (acts[hi - 1] < a_th or vels[hi - 1] > v_th):
        hi -= 1
    return poses[lo:hi]


# ── 정렬 / 전환 ──────────────────────────────────────────────────────────────

def _align(poses, pos_ref, yaw_target):
    """poses(클립 복사본)를 정렬.

    - yaw_target(rad) 을 바라보도록 클립 전체를 Y축으로 회전
    - 회전 후 시작점 XZ 를 pos_ref.root_pos 의 XZ 에 맞춤 (수직 Y 는 클립 고유값 유지)
    """
    first = poses[0]
    q_align = glm.angleAxis(yaw_target - _heading_yaw(first.rotations[0]), glm.vec3(0, 1, 0))

    bf = q_align * first.root_pos
    sx = pos_ref.root_pos.x - bf.x
    sz = pos_ref.root_pos.z - bf.z

    for p in poses:
        p.rotations[0] = glm.normalize(q_align * p.rotations[0])
        rp = q_align * p.root_pos
        p.root_pos = glm.vec3(rp.x + sx, rp.y, rp.z + sz)


def _transition(b_last, c_first, n):
    """b_last(B) → c_first(C) 로 n개의 전환 Pose 생성.

    t 를 0→1 로 선형 증가시키며 보간한다.
      - root 위치(3 DOF): 성분 선형보간(lerp) A = B(1-t) + C·t
      - 모든 joint 회전 DOF: quaternion 구면 선형보간(slerp)
    smoothstep 이징을 쓰지 않으므로 전환 시작/끝에서 속도가 0이 되며 생기던
    "멈칫" 끊김이 사라진다.
    """
    out = []
    njoints = len(b_last.rotations)
    for k in range(1, n + 1):
        t = k / (n + 1.0)                                   # 선형 0→1
        u = 1.0 - t
        root_pos = b_last.root_pos * u + c_first.root_pos * t          # lerp: B(1-t)+Ct
        rots = [_slerp(b_last.rotations[i], c_first.rotations[i], t)
                for i in range(njoints)]
        out.append(Pose(root_pos, rots))
    return out


# ── MotionSequence ───────────────────────────────────────────────────────────

class MotionSequence:
    """동일 골격 BVH 클립들을 트리밍·정렬·전환 보간해 단일 poses 타임라인으로 합친 것."""

    def __init__(self, clips, transition_frames=48, loop_transition=True,
                 last_matches_first_dir=True):
        assert clips, "clips 비어 있음"
        self.frame_time = clips[0].frame_time
        self.transition_frames = transition_frames
        self.segments = []          # [(start, end, label)] — 디버그용
        self.poses = self._build(clips, transition_frames, loop_transition,
                                 last_matches_first_dir)
        self.num_frames = len(self.poses)

    def _build(self, clips, T, loop_transition, last_matches_first_dir):
        # 0) 클립별 Pose 복사 + 선행/후행 T자 트리밍
        seqs = [_trim_rest([p.copy() for p in c.poses]) for c in clips]

        # 1) 정렬: 위치는 직전 클립 끝, 방향은 직전 클립 끝(진행방향 연속)
        #    단, 마지막 클립은 처음 클립과 같은 방향으로.
        clip0_yaw = _heading_yaw(seqs[0][0].rotations[0])
        for i in range(1, len(seqs)):
            prev_end = seqs[i - 1][-1]
            if last_matches_first_dir and i == len(seqs) - 1:
                yaw = clip0_yaw
            else:
                yaw = _heading_yaw(prev_end.rotations[0])
            _align(seqs[i], prev_end, yaw)

        # 2) 통합 타임라인 (사이마다 전환 구간)
        out = []
        for i, s in enumerate(seqs):
            if i > 0:
                tr = _transition(out[-1], s[0], T)
                self._add_segment(len(out), len(tr), f"trans->clip{i}")
                out.extend(tr)
            self._add_segment(len(out), len(s), f"clip{i}")
            out.extend(s)

        # 3) (옵션) 마지막 → 처음 전환으로 루프 매끄럽게
        if loop_transition and len(out) > 1:
            tr = _transition(out[-1], out[0], T)
            self._add_segment(len(out), len(tr), "trans->loop")
            out.extend(tr)

        return out

    def _add_segment(self, start, length, label):
        if length > 0:
            self.segments.append((start, start + length, label))

    def label_at(self, frame):
        for s, e, lbl in self.segments:
            if s <= frame < e:
                return lbl
        return "?"


if __name__ == '__main__':
    import os
    from bvh_loader import parse_bvh
    here = os.path.dirname(os.path.abspath(__file__))
    walk = parse_bvh(os.path.join(here, 'walk.bvh'), target_height=3.0)
    dance = parse_bvh(os.path.join(here, 'dance2.bvh'), target_height=3.0)

    seq = MotionSequence([walk, dance, walk], transition_frames=48)
    print(f"clips raw: walk({walk.num_frames}) dance({dance.num_frames})")
    print(f"total timeline frames = {seq.num_frames} (frame_time={seq.frame_time:.6f})")
    for s, e, lbl in seq.segments:
        print(f"  [{s:5d}, {e:5d})  {lbl}")

    N = seq.num_frames

    def jumpxz(i, j):
        a, b = seq.poses[i % N].root_pos, seq.poses[j % N].root_pos
        return glm.length(glm.vec3(a.x - b.x, 0.0, a.z - b.z))

    def act(i):
        return _pose_activity(seq.poses[i % N])

    print("\n경계: XZ 점프(연속이면 작음) / 전환 양끝 활성도(deg, T자면 작음):")
    for s, e, lbl in seq.segments:
        if lbl.startswith("trans"):
            print(f"  {lbl}: 진입XZ={jumpxz(s-1, s):.4f} 이탈XZ={jumpxz(e-1, e):.4f} "
                  f"| act[{s-1}]={act(s-1):.0f} act[{e}]={act(e):.0f}")
