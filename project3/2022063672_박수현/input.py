from glfw.GLFW import *
import numpy as np

g_cam_ang = 0.       # 수평 회전각 (azimuth)
g_cam_elev = 0.      # 수직 회전각 (elevation)
g_cam_dist = 5.      # 회전 중심점까지의 거리

g_pan_x = 0.
g_pan_y = 0.
g_pan_z = 0.

g_mouse_left_pressed = False
g_mouse_right_pressed = False
g_last_cursor_x = 0.
g_last_cursor_y = 0.

obj_spin = 0
obj_trans_x = 0
obj_trans_y = 0

# ── 재생 제어 상태 (main 이 읽고/쓴다) ─────────────────────────────────
g_playing     = True      # 재생/일시정지
g_play_speed  = 1.0       # 재생 속도 배율
g_cur_frame   = 0.0       # 현재 프레임(float). 재생 중 main 이 dt 만큼 증가
g_num_frames  = 1         # 전체 프레임 수 (main 이 시퀀스 구성 후 설정)

SPEED_STEP = 0.25
SPEED_MIN  = 0.25
SPEED_MAX  = 4.0

def mouse_button_callback(window, button, action, mods):
    global g_mouse_left_pressed, g_mouse_right_pressed, g_last_cursor_x, g_last_cursor_y
    if button == GLFW_MOUSE_BUTTON_LEFT:
        if action == GLFW_PRESS:
            g_mouse_left_pressed = True
            g_last_cursor_x, g_last_cursor_y = glfwGetCursorPos(window)
        elif action == GLFW_RELEASE:
            g_mouse_left_pressed = False
    elif button == GLFW_MOUSE_BUTTON_RIGHT:
        if action == GLFW_PRESS:
            g_mouse_right_pressed = True
            g_last_cursor_x, g_last_cursor_y = glfwGetCursorPos(window)
        elif action == GLFW_RELEASE:
            g_mouse_right_pressed = False

def cursor_pos_callback(window, xpos, ypos):
    global g_cam_ang, g_cam_elev, g_pan_x, g_pan_z, g_last_cursor_x, g_last_cursor_y
    dx = xpos - g_last_cursor_x
    dy = ypos - g_last_cursor_y
    g_last_cursor_x = xpos
    g_last_cursor_y = ypos

    if g_mouse_left_pressed:
        rot_speed = 0.005
        g_cam_ang  -= dx * rot_speed
        g_cam_elev += dy * rot_speed
        # 수직 각도 범위 제한 (뒤집히지 않도록)
        g_cam_elev = np.clip(g_cam_elev, -np.pi/2 + 0.01, np.pi/2 - 0.01)

    elif g_mouse_right_pressed:
        pan_speed = 0.005
        fwd_x = -np.sin(g_cam_ang)
        fwd_z = -np.cos(g_cam_ang)
        right_x =  np.cos(g_cam_ang)
        right_z = -np.sin(g_cam_ang)

        g_pan_x += dy * pan_speed * fwd_x
        g_pan_z += dy * pan_speed * fwd_z
        g_pan_x += -dx * pan_speed * right_x
        g_pan_z += -dx * pan_speed * right_z

def scroll_callback(window, xoffset, yoffset):
    global g_cam_dist

    scroll_speed = 0.3
    g_cam_dist += -yoffset * scroll_speed
    g_cam_dist = max(0.1, g_cam_dist)  # 너무 가까워지지 않도록

def key_callback(window, key, scancode, action, mods):
    global g_playing, g_play_speed, g_cur_frame
    if action != GLFW_PRESS and action != GLFW_REPEAT:
        return

    if key == GLFW_KEY_ESCAPE:
        glfwSetWindowShouldClose(window, GLFW_TRUE)

    elif key == GLFW_KEY_SPACE and action == GLFW_PRESS:
        g_playing = not g_playing                      # 재생/일시정지 토글

    elif key == GLFW_KEY_LEFT:                         # 한 프레임 뒤로 (스크럽 → 일시정지)
        g_playing = False
        g_cur_frame = (g_cur_frame - 1.0) % g_num_frames

    elif key == GLFW_KEY_RIGHT:                        # 한 프레임 앞으로 (스크럽 → 일시정지)
        g_playing = False
        g_cur_frame = (g_cur_frame + 1.0) % g_num_frames

    elif key == GLFW_KEY_RIGHT_BRACKET:                # ] 속도 증가
        g_play_speed = min(SPEED_MAX, g_play_speed + SPEED_STEP)

    elif key == GLFW_KEY_LEFT_BRACKET:                 # [ 속도 감소
        g_play_speed = max(SPEED_MIN, g_play_speed - SPEED_STEP)

    elif key == GLFW_KEY_R and action == GLFW_PRESS:   # 처음으로 리셋 + 재생
        g_cur_frame = 0.0
        g_playing = True