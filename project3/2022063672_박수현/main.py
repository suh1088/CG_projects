"""Project 3 — BVH Motion Viewer

 - obj_loader 로 stage.obj 로드 → 단일 VAO → Node 로 무대 배치 (Phong)
 - bvh_loader 로 walk/dance 골격 로드, motion_sequence 로 walk→dance→walk
   시퀀스 구성(위치·yaw 정렬 + slerp 전환 보간) → 민트색 박스 뼈대로 재생
 - P1 grid/axis/pivot 은 unlit, 카메라 orbit/pan/zoom (input.py 재활용)

이후 단계: 재생 제어 키(space/←→/속도/리셋), 관절 구, 모션 응용(궤적/잔상 등).
"""

import os
from OpenGL.GL import *
from glfw.GLFW import *
import glm
import numpy as np

from shaders import (
    load_shaders,
    g_vertex_shader_src,    g_fragment_shader_src,      # unlit (grid/frame/pivot)
    g_vertex_shader_phong,  g_fragment_shader_phong,    # Phong (메시)
)
from vao import prepare_vao_frame, prepare_vao_pivot, prepare_vao_grid
from obj_loader import load_obj, make_vao, Node
from bvh_loader import parse_bvh
from motion_sequence import MotionSequence
from skeleton_render import make_box_vao, bone_matrix
import input as inp


# ──────────────────────────────────────────────────────────────────────
# Lighting parameters
# ──────────────────────────────────────────────────────────────────────
LIGHT_POS   = glm.vec3(0.0, 12.0, 8.0)
LIGHT_COLOR = glm.vec3(1.00, 0.97, 0.95)
KA, KD, KS  = 0.25, 0.75, 0.40

STAGE_COLOR    = glm.vec3(0.72, 0.52, 0.34)   # 밝은 갈색
SKELETON_COLOR = glm.vec3(0.40, 0.92, 0.74)   # 민트색 뼈대

SKELETON_HEIGHT = 2.5     # 골격 목표 키 (직전 2.0 → 1.5배)
BONE_THICK      = 0.06    # 뼈(박스) 단면 두께 (골격 비율 유지 위해 함께 스케일)
STAGE_SCALE     = 1.5     # 무대 스케일 (직전 2.0 → 1.5배)
SKELETON_Y_TRANSLATE = 0.8 # 무대 높이 보정

CODE_DIR = os.path.dirname(os.path.abspath(__file__))


def build_stage():
    """stage.obj 의 모든 sub-object 를 합쳐 단일 VAO 로 빌드하고 Node 로 반환.

    stage.obj 바닥(카펫/계단 base)은 이미 y≈0 평면에 작성돼 있으므로
    별도 변환 없이 단위 배치하면 무대 윗면이 y=0 이 된다.
    (이후 골격의 발이 y=0 에 서도록 §3.3 에서 골격 수직 오프셋을 맞춘다.)
    """
    groups = load_obj(os.path.join(CODE_DIR, 'stage.obj'))

    # 거대한 바닥 판들 제외: Plane(y≈-0.79), Raining_lights_carpet(y≈-0.05)
    EXCLUDE = {'Plane', 'Raining_lights_carpet'}

    flat = []
    for name, g in groups.items():
        if name in EXCLUDE:
            continue
        flat.extend(g)
    vao, count = make_vao(flat)

    # 무대 로컬 bbox (골격 배치 기준용) — 위치는 인덱스 0,1,2
    xs, ys, zs = flat[0::6], flat[1::6], flat[2::6]
    bbox = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

    stage = Node(None, glm.mat4(), STAGE_COLOR)
    stage.set_vao(vao)
    stage.set_vertex_count(count)
    stage.set_transform(glm.scale(glm.mat4(1.0), glm.vec3(STAGE_SCALE)))   # 스케일, 바닥 y≈0 유지
    return stage, bbox


def main():
    if not glfwInit():
        return
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3)
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3)
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE)

    window = glfwCreateWindow(3200, 1600, 'P3_BVH_viewer', None, None)
    if not window:
        glfwTerminate()
        return
    glfwMakeContextCurrent(window)

    glfwSetKeyCallback(window,         inp.key_callback)
    glfwSetMouseButtonCallback(window, inp.mouse_button_callback)
    glfwSetCursorPosCallback(window,   inp.cursor_pos_callback)
    glfwSetScrollCallback(window,      inp.scroll_callback)

    prog_unlit = load_shaders(g_vertex_shader_src,   g_fragment_shader_src)
    prog_phong = load_shaders(g_vertex_shader_phong, g_fragment_shader_phong)

    loc_unlit_MVP = glGetUniformLocation(prog_unlit, 'MVP')

    loc_MVP            = glGetUniformLocation(prog_phong, 'MVP')
    loc_M              = glGetUniformLocation(prog_phong, 'M')
    loc_NormalMatrix   = glGetUniformLocation(prog_phong, 'NormalMatrix')
    loc_view_pos       = glGetUniformLocation(prog_phong, 'view_pos')
    loc_light_pos      = glGetUniformLocation(prog_phong, 'light_pos')
    loc_light_color    = glGetUniformLocation(prog_phong, 'light_color')
    loc_material_color = glGetUniformLocation(prog_phong, 'material_color')
    loc_shininess      = glGetUniformLocation(prog_phong, 'shininess')
    loc_ka             = glGetUniformLocation(prog_phong, 'ka')
    loc_kd             = glGetUniformLocation(prog_phong, 'kd')
    loc_ks             = glGetUniformLocation(prog_phong, 'ks')

    vao_frame = prepare_vao_frame()
    vao_pivot = prepare_vao_pivot()
    vao_grid, grid_vertex_count = prepare_vao_grid()

    # ── 무대 로드/배치 ───────────────────────────────────────────────
    stage, stage_bbox = build_stage()
    stage.update_tree_global_transform()

    # ── 골격 로드 + walk→dance→walk 시퀀스 구성 ──────────────────────
    walk  = parse_bvh(os.path.join(CODE_DIR, 'walk.bvh'),   target_height=SKELETON_HEIGHT)
    walk_stop  = parse_bvh(os.path.join(CODE_DIR, 'walk_stop.bvh'),   target_height=SKELETON_HEIGHT)
    dance = parse_bvh(os.path.join(CODE_DIR, 'dance2.bvh'), target_height=SKELETON_HEIGHT)
    seq = MotionSequence([walk_stop, dance, walk], transition_frames=60, loop_transition=False)   # 1초 전환, 루프 복귀는 보간 없음
    rig = walk                       # 동일 골격 → 아무 클립이나 apply_pose 용 rig 로 사용
    box_vao, box_count = make_box_vao()
    inp.g_num_frames = seq.num_frames     # 재생 제어(input.py)에 전체 프레임 수 전달
    print(f"[sequence] {seq.num_frames} frames | "
          + ", ".join(f"{lbl}[{s}:{e}]" for s, e, lbl in seq.segments))

    # 발 최저점(지면 정렬용) 산출
    g_min_y = float('inf')
    for p in seq.poses:
        rig.apply_pose(p)
        for j in rig.joints:
            y = glm.vec3(j.global_transform[3]).y
            if y < g_min_y:
                g_min_y = y
    root0 = seq.poses[0].root_pos

    # 첫 walk(clip0) 의 진행방향을 world -x 로 회전시킬 yaw 계산
    c0s, c0e = next((s, e) for s, e, lbl in seq.segments if lbl == 'clip0')
    ps, pe = seq.poses[c0s].root_pos, seq.poses[c0e - 1].root_pos
    beta = float(np.arctan2(pe.x - ps.x, pe.z - ps.z))     # 현재 진행방향
    theta = -np.pi / 2.0 - beta                            # -x 방향(atan2=-pi/2)으로 정렬

    # 무대 +x 쪽 바닥에서 출발 (무대 bbox 중심 기준)
    S = STAGE_SCALE
    cx = 0.5 * (stage_bbox[0] + stage_bbox[1]) * S
    cz = 0.5 * (stage_bbox[4] + stage_bbox[5]) * S
    wx = (stage_bbox[1] - stage_bbox[0]) * S
    start_pos = glm.vec3(cx + 0.40 * wx - 3.0, SKELETON_Y_TRANSLATE, cz)   # +x 가장자리(-x로 1 이동), 무대 높이만큼 올림
    print(f"[placement] start={tuple(round(v,2) for v in start_pos)} "
          f"theta={np.degrees(theta):.1f}deg (walk -> -x), y_lift={SKELETON_Y_TRANSLATE}")

    # 모델 변환: 시작을 원점으로 → yaw 회전(-x 정렬) → 무대 +x 위치로 이동, 발=y0
    M_model = (glm.translate(glm.mat4(1.0), start_pos)
               * glm.rotate(glm.mat4(1.0), float(theta), glm.vec3(0, 1, 0))
               * glm.translate(glm.mat4(1.0), glm.vec3(-root0.x, -g_min_y, -root0.z)))

    # ── 렌더 루프 ──────────────────────────────────────────────────
    glEnable(GL_DEPTH_TEST)
    prev_time = glfwGetTime()

    while not glfwWindowShouldClose(window):
        glClearColor(0.06, 0.07, 0.09, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        w, h = glfwGetFramebufferSize(window)
        aspect = w / h if h else 1.0
        P = glm.perspective(glm.radians(45.0), aspect, 0.1, 300.0)

        cam_x = inp.g_cam_dist * np.cos(inp.g_cam_elev) * np.sin(inp.g_cam_ang) + inp.g_pan_x
        cam_y = inp.g_cam_dist * np.sin(inp.g_cam_elev)                          + inp.g_pan_y
        cam_z = inp.g_cam_dist * np.cos(inp.g_cam_elev) * np.cos(inp.g_cam_ang) + inp.g_pan_z
        cam_pos = glm.vec3(cam_x, cam_y, cam_z)
        V = glm.lookAt(cam_pos,
                       glm.vec3(inp.g_pan_x, inp.g_pan_y, inp.g_pan_z),
                       glm.vec3(0, 1, 0))
        VP = P * V

        # ── 1) unlit: grid / frame / pivot ──────────────────────────
        glUseProgram(prog_unlit)
        glUniformMatrix4fv(loc_unlit_MVP, 1, GL_FALSE, glm.value_ptr(VP))

        glBindVertexArray(vao_grid)
        glDrawArrays(GL_LINES, 0, grid_vertex_count)

        glBindVertexArray(vao_frame)
        glDrawArrays(GL_LINES, 0, 6)

        MVP_pivot = VP * glm.translate(glm.vec3(inp.g_pan_x, inp.g_pan_y, inp.g_pan_z))
        glUniformMatrix4fv(loc_unlit_MVP, 1, GL_FALSE, glm.value_ptr(MVP_pivot))
        glPointSize(10)
        glBindVertexArray(vao_pivot)
        glDrawArrays(GL_POINTS, 0, 1)

        # ── 2) Phong: 무대 ──────────────────────────────────────────
        glUseProgram(prog_phong)
        glUniform3fv(loc_view_pos,    1, glm.value_ptr(cam_pos))
        glUniform3fv(loc_light_pos,   1, glm.value_ptr(LIGHT_POS))
        glUniform3fv(loc_light_color, 1, glm.value_ptr(LIGHT_COLOR))
        glUniform1f(loc_ka, KA)
        glUniform1f(loc_kd, KD)
        glUniform1f(loc_ks, KS)

        M = stage.get_global_transform() * stage.get_shape_transform()
        MVP = VP * M
        NormalMatrix = glm.transpose(glm.inverse(glm.mat3(M)))

        glUniformMatrix4fv(loc_MVP,          1, GL_FALSE, glm.value_ptr(MVP))
        glUniformMatrix4fv(loc_M,            1, GL_FALSE, glm.value_ptr(M))
        glUniformMatrix3fv(loc_NormalMatrix, 1, GL_FALSE, glm.value_ptr(NormalMatrix))
        glUniform3fv(loc_material_color, 1, glm.value_ptr(stage.get_color()))
        glUniform1f(loc_shininess, 16.0)
        stage.draw()

        # ── 3) Phong: 골격(walk→dance→walk) 뼈대 박스 ───────────────
        # 재생 제어: 재생 중이면 dt·속도만큼 프레임 진행. (일시정지/스크럽/속도/리셋은 input.py)
        now = glfwGetTime()
        dt = now - prev_time
        prev_time = now
        if inp.g_playing:
            inp.g_cur_frame = (inp.g_cur_frame + dt * inp.g_play_speed / seq.frame_time) % seq.num_frames
        frame = int(inp.g_cur_frame) % seq.num_frames
        rig.apply_pose(seq.poses[frame])

        glUniform3fv(loc_material_color, 1, glm.value_ptr(SKELETON_COLOR))
        glUniform1f(loc_shininess, 32.0)
        glBindVertexArray(box_vao)
        for j in rig.joints:
            if j.parent is None:
                continue
            p0 = glm.vec3(M_model * glm.vec4(glm.vec3(j.parent.global_transform[3]), 1.0))
            p1 = glm.vec3(M_model * glm.vec4(glm.vec3(j.global_transform[3]),        1.0))
            Mb = bone_matrix(p0, p1, BONE_THICK)
            if Mb is None:
                continue
            MVP = VP * Mb
            NM = glm.transpose(glm.inverse(glm.mat3(Mb)))
            glUniformMatrix4fv(loc_MVP,          1, GL_FALSE, glm.value_ptr(MVP))
            glUniformMatrix4fv(loc_M,            1, GL_FALSE, glm.value_ptr(Mb))
            glUniformMatrix3fv(loc_NormalMatrix, 1, GL_FALSE, glm.value_ptr(NM))
            glDrawArrays(GL_TRIANGLES, 0, box_count)

        glfwSwapBuffers(window)
        glfwPollEvents()

    glfwTerminate()


if __name__ == "__main__":
    main()
