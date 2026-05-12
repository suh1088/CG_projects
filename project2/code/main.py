import os
from OpenGL.GL import *
from glfw.GLFW import *
import glm
import numpy as np

from shaders import (
    load_shaders,
    g_vertex_shader_src,        g_fragment_shader_src,        # unlit (grid/frame)
    g_vertex_shader_phong,      g_fragment_shader_phong,      # Phong (meshes)
)
from vao import prepare_vao_frame, prepare_vao_pivot, prepare_vao_grid
from obj_loader import load_obj, make_vao, Mesh
import input as inp


# ──────────────────────────────────────────────────────────────────────
# Lighting parameters (plan §3.3)
# ──────────────────────────────────────────────────────────────────────
LIGHT_POS    = glm.vec3(8.0, 12.0, 8.0)
LIGHT_COLOR  = glm.vec3(1.00, 0.96, 0.96)
KA, KD, KS   = 0.20, 0.75, 0.55

CODE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    if not glfwInit():
        return
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3)
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3)
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE)

    window = glfwCreateWindow(3200, 1600, 'SuHyun_P2_viewer', None, None)
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

    # ── 메시 계층 정의 (parent, shape_transform, color) ──────────────
    lift = Mesh(None,
                glm.mat4(),
                glm.vec3(0.8, 0.3, 0.3))

                # glm.vec3(0.45, 0.47, 0.50))
    saturn = Mesh(None,
                  glm.scale(glm.vec3(0.8)),
                  glm.vec3(1, 1, 1))
    robot_arm_1 = Mesh(lift,
                       glm.scale(glm.vec3(0.20)),
                       glm.vec3(0.9686, 0.8667, 0.3294))
    robot_arm_2 = Mesh(robot_arm_1,
                       glm.scale(glm.vec3(0.20)),
                       glm.vec3(0.9686, 0.8667, 0.3294))
    robot_arm_3 = Mesh(robot_arm_2,
                       glm.scale(glm.vec3(0.20)),
                       glm.vec3(0.9686, 0.8667, 0.3294))

    # ── VAO / vertex count 할당 (setter) ────────────────────────────
    lift_subs   = load_obj(os.path.join(CODE_DIR, 'lift_plate.obj'))
    saturn_subs = load_obj(os.path.join(CODE_DIR, 'saturn_V_lp.obj'))
    arm_subs    = load_obj(os.path.join(CODE_DIR, 'robot_arm.obj'))

    def combine(groups, names=None):
        """선택된 sub-mesh 들을 합쳐 단일 VAO 로 빌드."""
        flat = []
        for n in (names if names is not None else groups.keys()):
            flat.extend(groups[n])
        return make_vao(flat)

    # robot_arm.obj 의 sub-object → 물리 부품 매핑 (bounding box 분석 기반)
    arm1_parts = ['Cylinder.002',              # 바닥판 (y=1.7)
                  'Cylinder.020_Cylinder.021', # 바닥 트림 (y=2.3)
                  'Cylinder.003']              # 기둥 (y=2.3→5.7)
    arm2_parts = ['Cylinder.019',              # 첫번째 높은 팔 (y=5.3→10.7)
                  'Cylinder.017_Cylinder.014'] # 기둥-팔 조인트
    arm3_parts = ['Cylinder.018_Cylinder.020', # 낮은 팔 / 손 (y~10)
                  'Cylinder.021_Cylinder.022',
                  'Cylinder.022_Cylinder.023',
                  'Cylinder.026_Cylinder.027',
                  'Cylinder.014_Cylinder.026']

    lift_vao,   lift_count   = combine(lift_subs)
    saturn_vao, saturn_count = combine(saturn_subs)
    arm1_vao,   arm1_count   = combine(arm_subs, arm1_parts)
    arm2_vao,   arm2_count   = combine(arm_subs, arm2_parts)
    arm3_vao,   arm3_count   = combine(arm_subs, arm3_parts)

    lift.set_vao(lift_vao);             lift.set_vertex_count(lift_count)
    saturn.set_vao(saturn_vao);         saturn.set_vertex_count(saturn_count)
    robot_arm_1.set_vao(arm1_vao);      robot_arm_1.set_vertex_count(arm1_count)
    robot_arm_2.set_vao(arm2_vao);      robot_arm_2.set_vertex_count(arm2_count)
    robot_arm_3.set_vao(arm3_vao);      robot_arm_3.set_vertex_count(arm3_count)

    roots  = [lift, saturn]
    meshes = [lift, saturn, robot_arm_1, robot_arm_2, robot_arm_3]

    # ── 렌더 루프 ──────────────────────────────────────────────────
    glEnable(GL_DEPTH_TEST)

    while not glfwWindowShouldClose(window):
        glClearColor(0.08, 0.09, 0.11, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        w, h = glfwGetFramebufferSize(window)
        aspect = w / h if h else 1.0
        P = glm.perspective(glm.radians(45.0), aspect, 0.1, 200.0)

        cam_x = inp.g_cam_dist * np.cos(inp.g_cam_elev) * np.sin(inp.g_cam_ang) + inp.g_pan_x
        cam_y = inp.g_cam_dist * np.sin(inp.g_cam_elev)                          + inp.g_pan_y
        cam_z = inp.g_cam_dist * np.cos(inp.g_cam_elev) * np.cos(inp.g_cam_ang) + inp.g_pan_z
        cam_pos = glm.vec3(cam_x, cam_y, cam_z)
        V = glm.lookAt(cam_pos,
                       glm.vec3(inp.g_pan_x, inp.g_pan_y, inp.g_pan_z),
                       glm.vec3(0, 1, 0))
        VP = P * V

        # ── 1) unlit: grid / frame / pivot ───────────────────────────
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

        # ── 2) Phong: 메시 ──────────────────────────────────────────
        glUseProgram(prog_phong)

        glUniform3fv(loc_view_pos,    1, glm.value_ptr(cam_pos))
        glUniform3fv(loc_light_pos,   1, glm.value_ptr(LIGHT_POS))
        glUniform3fv(loc_light_color, 1, glm.value_ptr(LIGHT_COLOR))
        glUniform1f(loc_ka, KA)
        glUniform1f(loc_kd, KD)
        glUniform1f(loc_ks, KS)

        t = glfwGetTime()

        saturn.set_transform(glm.translate((5,1,1))* 
                             glm.rotate(np.radians(45),glm.vec3(1,0,0))*
                             glm.rotate(np.radians(90),glm.vec3(0,0,1)))
        
        lift.set_transform(glm.translate((6*np.sin(t*0.1),0,0))*
                           glm.translate((0,0,-2))*
                           glm.rotate(np.radians(180),glm.vec3(0,1,0)))
        
        robot_arm_1.set_transform(glm.translate((2, 0,-0.5))*
                                  glm.rotate(np.radians(90),glm.vec3(0,1,0)))
        
        # 관절점은 OBJ 좌표계 기준 위치에 shape_transform 의 scale(0.20) 을 곱한 값.
        # arm2 의 어깨 관절: 기둥(Cylinder.003) 위, arm2 기하 바닥 ≈ (1.83, 5.30, -1.08)
        # arm3 의 팔꿈치 관절: arm2 끝의 hinge(Cylinder.014_Cylinder.026) 중심 ≈ (1.83, 10.15, -1.08)
        shoulder = glm.vec3(1.83, 6, -1.08) * 0.20
        elbow    = glm.vec3(1.83, 10.15, -1.08) * 0.20

        robot_arm_2.set_transform(glm.translate(shoulder) *
                                  glm.rotate(-np.abs(np.sin(t*0.7)), glm.vec3(0,0,1)) *
                                  glm.translate(-shoulder))

        robot_arm_3.set_transform(glm.translate(elbow) *
                                  glm.rotate(0.5*np.sin(t*2), glm.vec3(0,0,1)) *
                                  glm.translate(-elbow))

        for root in roots:
            root.update_tree_global_transform()

        for mesh in meshes:
            if mesh.vao is None:
                continue
            M = mesh.get_global_transform() * mesh.get_shape_transform()
            MVP = VP * M
            NormalMatrix = glm.transpose(glm.inverse(glm.mat3(M)))

            glUniformMatrix4fv(loc_MVP,          1, GL_FALSE, glm.value_ptr(MVP))
            glUniformMatrix4fv(loc_M,            1, GL_FALSE, glm.value_ptr(M))
            glUniformMatrix3fv(loc_NormalMatrix, 1, GL_FALSE, glm.value_ptr(NormalMatrix))

            glUniform3fv(loc_material_color, 1, glm.value_ptr(mesh.get_color()))
            glUniform1f(loc_shininess, 32.0)
            mesh.draw()

        glfwSwapBuffers(window)
        glfwPollEvents()

    glfwTerminate()


if __name__ == "__main__":
    main()
