"""OBJ 로더 + Mesh (VAO) 빌더.

plan.md §3.1 에 따른 메시 처리 설계:
 - fan triangulation 으로 tri / quad / n-gon 을 단일 코드 패스에서 처리
 - 정점 단위(position+normal) 데이터를 VBO 에 그대로 복제 (un-indexed)
   → OBJ 의 분리 인덱스(pos vs normal) 차이를 그대로 보존할 수 있음
 - vn 이 없는 면은 cross product face normal 로 fallback
 - 파일 내부 `o name` 블록마다 별도의 Mesh 인스턴스로 분리 →
   계층 구조 설계 단계에서 sub-object 단위 transform 부여가 가능
"""

import ctypes
import numpy as np
from OpenGL.GL import *
import glm


# ── Mesh ────────────────────────────────────────────────────────────────────

class Mesh:
    def __init__(self, parent, shape_transform, color):
        self.vao = None
        self.vertex_count = 0
        self.parent = parent
        self.children = []
        if parent is not None:
            parent.children.append(self)

        # transform
        self.transform = glm.mat4()
        self.global_transform = glm.mat4()

        # shape
        self.shape_transform = shape_transform
        self.color = color

    def draw(self):
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES, 0, self.vertex_count)

    def set_vao(self, vao):
        self.vao = vao

    def set_vertex_count(self, vertex_count):
        self.vertex_count = vertex_count

    def set_shape_transform(self, shape_transform):
        self.shape_transform = shape_transform

    def set_transform(self, transform):
        self.transform = transform

    def update_tree_global_transform(self):
        if self.parent is not None:
            self.global_transform = self.parent.get_global_transform() * self.transform
        else:
            self.global_transform = self.transform

        for child in self.children:
            child.update_tree_global_transform()

    def get_global_transform(self):
        return self.global_transform
    def get_shape_transform(self):
        return self.shape_transform
    def get_color(self):
        return self.color
    



# ── 내부 VAO 빌더 ─────────────────────────────────────────────────────────

# layout: 6 floats per vertex (attr0: position xyz, attr1: normal xyz)
_STRIDE  = 6 * 4                    # 24 bytes
_OFFSET3 = ctypes.c_void_p(3 * 4)   # 12 bytes

def make_vao(flat):
    """flat: Python list of floats [px,py,pz, nx,ny,nz, ...]"""
    arr  = np.array(flat, dtype=np.float32)
    data = arr.tobytes()

    vao = glGenVertexArrays(1)
    glBindVertexArray(vao)

    vbo = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, len(data), data, GL_STATIC_DRAW)

    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, _STRIDE, None)
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, _STRIDE, _OFFSET3)
    glEnableVertexAttribArray(1)

    glBindVertexArray(0)
    return vao, len(arr) // 6


# ── OBJ 파서 ─────────────────────────────────────────────────────────────

def load_obj(path):
    """OBJ → {object_name: flat_float_list}  (파일 내 `o` 블록 순서 유지).

    각 그룹의 raw vertex stream 을 반환한다. 호출측에서 원하는 그룹을 골라
    합쳐 `make_vao()` 로 단일 VAO 를 만들고, Mesh setter 로 주입한다.
    """
    positions = []   # [(x,y,z), ...]
    normals   = []   # [(nx,ny,nz), ...]

    groups  = {}                 # name → flat float list
    current = '__default__'
    groups[current] = []

    with open(path, encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line or line[0] == '#':
                continue
            tok = line.split()
            tag = tok[0]

            if tag == 'v':
                positions.append((float(tok[1]), float(tok[2]), float(tok[3])))

            elif tag == 'vn':
                normals.append((float(tok[1]), float(tok[2]), float(tok[3])))

            elif tag == 'vt':
                pass   # UV 미사용

            elif tag == 'o':
                name = tok[1] if len(tok) > 1 else '__obj__'
                # 같은 이름 충돌 방지
                unique, n = name, 1
                while unique in groups:
                    unique = f'{name}_{n}'
                    n += 1
                groups[unique] = []
                current = unique

            elif tag == 'f':
                face = []
                for t in tok[1:]:
                    parts = t.split('/')
                    pi = int(parts[0])
                    pi = pi - 1 if pi > 0 else len(positions) + pi  # 1-based & 음수 처리

                    ni = None
                    if len(parts) == 3 and parts[2]:
                        ni = int(parts[2])
                        ni = ni - 1 if ni > 0 else len(normals) + ni

                    face.append((pi, ni))

                if len(face) < 3:
                    continue

                # fan triangulation: (v0,v1,v2), (v0,v2,v3), ...
                for i in range(1, len(face) - 1):
                    tri = (face[0], face[i], face[i + 1])

                    # 하나라도 normal 누락이면 face normal 로 fallback
                    if any(v[1] is None for v in tri):
                        p0 = glm.vec3(*positions[tri[0][0]])
                        p1 = glm.vec3(*positions[tri[1][0]])
                        p2 = glm.vec3(*positions[tri[2][0]])
                        cross  = glm.cross(p1 - p0, p2 - p0)
                        length = glm.length(cross)
                        fn = cross / length if length > 1e-8 else glm.vec3(0, 1, 0)
                        nx, ny, nz = fn.x, fn.y, fn.z
                        for pi, _ in tri:
                            px, py, pz = positions[pi]
                            groups[current] += [px, py, pz, nx, ny, nz]
                    else:
                        for pi, ni in tri:
                            px, py, pz = positions[pi]
                            nx, ny, nz = normals[ni]
                            groups[current] += [px, py, pz, nx, ny, nz]

    result = {}
    for name, flat in groups.items():
        if not flat:
            continue
        result[name] = flat
        print(f"  [{name}] {len(flat)//6} vertices")
    return result
