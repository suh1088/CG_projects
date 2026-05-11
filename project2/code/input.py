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
    global g_cam_ang, g_cam_elev, obj_spin, obj_trans_x, obj_trans_y
    if key==GLFW_KEY_ESCAPE and action==GLFW_PRESS:
        glfwSetWindowShouldClose(window, GLFW_TRUE)
    else:
        if action==GLFW_PRESS or action==GLFW_REPEAT:
            if key==GLFW_KEY_1:
                g_cam_ang += np.radians(-10)
            elif key==GLFW_KEY_3:
                g_cam_ang += np.radians(10)
            elif key==GLFW_KEY_2:
                g_cam_elev += np.radians(5)
                g_cam_elev = np.clip(g_cam_elev, -np.pi/2 + 0.01, np.pi/2 - 0.01)
            elif key==GLFW_KEY_W:
                g_cam_elev -= np.radians(5)
                g_cam_elev = np.clip(g_cam_elev, -np.pi/2 + 0.01, np.pi/2 - 0.01)

            elif key==GLFW_KEY_U:
                obj_spin += -.1
            elif key==GLFW_KEY_O:
                obj_spin += .1

            elif key==GLFW_KEY_LEFT:
                obj_trans_x += -.1
            elif key==GLFW_KEY_RIGHT:
                obj_trans_x += .1

            elif key==GLFW_KEY_DOWN:
                obj_trans_y += -.1
            elif key==GLFW_KEY_UP:
                obj_trans_y += .1
