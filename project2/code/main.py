from OpenGL.GL import *
from glfw.GLFW import *
import glm
import numpy as np
from shaders import load_shaders, g_vertex_shader_src, g_fragment_shader_src
from vao import prepare_vao_cube_, prepare_vao_frame, prepare_vao_grid
import input as inp

def main():
    # initialize glfw
    if not glfwInit():
        return
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3)   # OpenGL 3.3
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3)
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE)  # Do not allow legacy OpenGl API calls

    # create a window and OpenGL context
    window = glfwCreateWindow(3200, 1600, 'SuHyun_P1_viewer', None, None)
    if not window:
        glfwTerminate()
        return
    glfwMakeContextCurrent(window)

    # register event callbacks
    glfwSetKeyCallback(window, inp.key_callback)
    glfwSetMouseButtonCallback(window, inp.mouse_button_callback)
    glfwSetCursorPosCallback(window, inp.cursor_pos_callback)
    glfwSetScrollCallback(window, inp.scroll_callback)

    # load shaders
    shader_program = load_shaders(g_vertex_shader_src, g_fragment_shader_src)

    # get uniform locations
    loc_MVP = glGetUniformLocation(shader_program, 'MVP')

    # prepare vaos
    vao_cube = prepare_vao_cube_()
    vao_frame = prepare_vao_frame()
    vao_grid, grid_vertex_count = prepare_vao_grid()

    # loop until the user closes the window
    while not glfwWindowShouldClose(window):
        # render

        # enable depth test (we'll see details later)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)

        glUseProgram(shader_program)

        # render in "wireframe mode"
        # glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)

        # projection matrix
        P = glm.perspective(glm.radians(45.), 2., .1, 100.)

        # view matrix
        # rotate camera position with g_cam_ang / move camera up & down with g_cam_height
        cam_x = inp.g_cam_dist*np.cos(inp.g_cam_elev)*np.sin(inp.g_cam_ang) + inp.g_pan_x
        cam_y = inp.g_cam_dist*np.sin(inp.g_cam_elev) + inp.g_pan_y
        cam_z = inp.g_cam_dist*np.cos(inp.g_cam_elev)*np.cos(inp.g_cam_ang) + inp.g_pan_z
        V = glm.lookAt(glm.vec3(cam_x, cam_y, cam_z), glm.vec3(inp.g_pan_x, inp.g_pan_y, inp.g_pan_z), glm.vec3(0,1,0))

        # current frame: P*V*I (now this is the world frame)
        I = glm.mat4()
        MVP = P*V*I
        glUniformMatrix4fv(loc_MVP, 1, GL_FALSE, glm.value_ptr(MVP))

        # draw current frame
        glBindVertexArray(vao_frame)
        glDrawArrays(GL_LINES, 0, 6)

        # draw grid on xz plane
        glBindVertexArray(vao_grid)
        glDrawArrays(GL_LINES, 0, grid_vertex_count)

        # draw cube
        glBindVertexArray(vao_cube)
        glDrawArrays(GL_TRIANGLES, 0, 36)

        # swap front and back buffers
        glfwSwapBuffers(window)

        # poll events
        glfwPollEvents()

    # terminate glfw
    glfwTerminate()

if __name__ == "__main__":
    main()
