"""골격 렌더 지오메트리 + 뼈 배치 헬퍼 (plan.md §5)

뼈(bone)를 **직육면체(box)** 로 표현한다.
 - 단위 박스: x,z ∈ [-0.5, 0.5], y ∈ [0, 1]  (밑면이 원점, +Y 로 길이 1)
 - 뼈는 부모 joint → 자식 joint 를 잇는 선분. 단위 박스를
   `translate(p0) · R(+Y→방향) · scale(thick, length, thick)` 로 배치.
 - position+normal 인터리브 → obj_loader.make_vao 와 동일 attrib(loc0 pos, loc1 normal).
"""

import glm
from obj_loader import make_vao


def make_box_vao():
    """단위 박스 VAO. x,z∈[-0.5,0.5], y∈[0,1]. (vao, vertex_count) 반환."""
    x0, x1 = -0.5, 0.5
    y0, y1 = 0.0, 1.0
    z0, z1 = -0.5, 0.5

    # (normal, [4 corners ccw])
    faces = [
        ((0, 0, 1),  [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),  # +z
        ((0, 0, -1), [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)]),  # -z
        ((1, 0, 0),  [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)]),  # +x
        ((-1, 0, 0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]),  # -x
        ((0, 1, 0),  [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)]),  # +y
        ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),  # -y
    ]

    flat = []
    for n, (a, b, c, d) in faces:
        for tri in ((a, b, c), (a, c, d)):
            for v in tri:
                flat += [v[0], v[1], v[2], n[0], n[1], n[2]]
    return make_vao(flat)


def _quat_from_to(a, b):
    """단위벡터 a 를 b 로 회전시키는 quaternion."""
    a = glm.normalize(a)
    b = glm.normalize(b)
    d = glm.dot(a, b)
    if d > 0.99999:
        return glm.quat()                                  # 동일 방향 → identity
    if d < -0.99999:                                       # 정반대 → 임의 수직축 180°
        axis = glm.cross(glm.vec3(1, 0, 0), a)
        if glm.length(axis) < 1e-6:
            axis = glm.cross(glm.vec3(0, 0, 1), a)
        return glm.angleAxis(glm.pi(), glm.normalize(axis))
    axis = glm.normalize(glm.cross(a, b))
    angle = glm.acos(max(-1.0, min(1.0, d)))
    return glm.angleAxis(angle, axis)


def bone_matrix(p0, p1, thickness):
    """p0(부모)→p1(자식) 을 잇는 단위 박스의 모델 행렬. 길이 0 이면 None."""
    d = p1 - p0
    L = glm.length(d)
    if L < 1e-6:
        return None
    R = glm.mat4_cast(_quat_from_to(glm.vec3(0, 1, 0), d / L))
    return glm.translate(glm.mat4(1.0), p0) * R * glm.scale(glm.mat4(1.0), glm.vec3(thickness, L, thickness))
