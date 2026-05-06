from OpenGL.GL import *
import glm
import ctypes

def prepare_vao_triangle():
    # prepare vertex data (in main memory)
    vertices = glm.array(glm.float32,
        # position        # color
         0.0, 0.0, 0.0,  1.0, 0.0, 0.0, # v0
         0.5, 0.0, 0.0,  0.0, 1.0, 0.0, # v1
         0.0, 0.5, 0.0,  0.0, 0.0, 1.0, # v2
    )

    # create and activate VAO (vertex array object)
    VAO = glGenVertexArrays(1)  # create a vertex array object ID and store it to VAO variable
    glBindVertexArray(VAO)      # activate VAO

    # create and activate VBO (vertex buffer object)
    VBO = glGenBuffers(1)   # create a buffer object ID and store it to VBO variable
    glBindBuffer(GL_ARRAY_BUFFER, VBO)  # activate VBO as a vertex buffer object

    # copy vertex data to VBO
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.ptr, GL_STATIC_DRAW)

    # configure vertex positions
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), None)
    glEnableVertexAttribArray(0)

    # configure vertex colors
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), ctypes.c_void_p(3*glm.sizeof(glm.float32)))
    glEnableVertexAttribArray(1)

    return VAO

def prepare_vao_cube():
    # 정육면체: 중심 원점, 한 변의 길이 0.5 (각 꼭짓점 ±0.25)
    # 6면 × 2삼각형 × 3정점 = 36 정점, 각 정점은 (position xyz, color rgb)
    # 파스텔 색상: 각 면마다 부드러운 색상 적용
    vertices = glm.array(glm.float32,
        # front face (z=+0.25) - pastel pink
        -0.25, -0.25,  0.25,  1.00, 0.71, 0.76,
         0.25, -0.25,  0.25,  1.00, 0.71, 0.76,
         0.25,  0.25,  0.25,  1.00, 0.71, 0.76,
        -0.25, -0.25,  0.25,  1.00, 0.71, 0.76,
         0.25,  0.25,  0.25,  1.00, 0.71, 0.76,
        -0.25,  0.25,  0.25,  1.00, 0.71, 0.76,
        # back face (z=-0.25) - pastel mint
         0.25, -0.25, -0.25,  0.60, 0.90, 0.80,
        -0.25, -0.25, -0.25,  0.60, 0.90, 0.80,
        -0.25,  0.25, -0.25,  0.60, 0.90, 0.80,
         0.25, -0.25, -0.25,  0.60, 0.90, 0.80,
        -0.25,  0.25, -0.25,  0.60, 0.90, 0.80,
         0.25,  0.25, -0.25,  0.60, 0.90, 0.80,
        # left face (x=-0.25) - pastel green
        -0.25, -0.25, -0.25,  0.70, 0.90, 0.70,
        -0.25, -0.25,  0.25,  0.70, 0.90, 0.70,
        -0.25,  0.25,  0.25,  0.70, 0.90, 0.70,
        -0.25, -0.25, -0.25,  0.70, 0.90, 0.70,
        -0.25,  0.25,  0.25,  0.70, 0.90, 0.70,
        -0.25,  0.25, -0.25,  0.70, 0.90, 0.70,
        # right face (x=+0.25) - pastel lavender
         0.25, -0.25,  0.25,  0.80, 0.75, 0.95,
         0.25, -0.25, -0.25,  0.80, 0.75, 0.95,
         0.25,  0.25, -0.25,  0.80, 0.75, 0.95,
         0.25, -0.25,  0.25,  0.80, 0.75, 0.95,
         0.25,  0.25, -0.25,  0.80, 0.75, 0.95,
         0.25,  0.25,  0.25,  0.80, 0.75, 0.95,
        # top face (y=+0.25) - pastel sky blue
        -0.25,  0.25,  0.25,  0.67, 0.85, 0.95,
         0.25,  0.25,  0.25,  0.67, 0.85, 0.95,
         0.25,  0.25, -0.25,  0.67, 0.85, 0.95,
        -0.25,  0.25,  0.25,  0.67, 0.85, 0.95,
         0.25,  0.25, -0.25,  0.67, 0.85, 0.95,
        -0.25,  0.25, -0.25,  0.67, 0.85, 0.95,
        # bottom face (y=-0.25) - pastel peach
        -0.25, -0.25, -0.25,  1.00, 0.85, 0.70,
         0.25, -0.25, -0.25,  1.00, 0.85, 0.70,
         0.25, -0.25,  0.25,  1.00, 0.85, 0.70,
        -0.25, -0.25, -0.25,  1.00, 0.85, 0.70,
         0.25, -0.25,  0.25,  1.00, 0.85, 0.70,
        -0.25, -0.25,  0.25,  1.00, 0.85, 0.70,
    )

    VAO = glGenVertexArrays(1)
    glBindVertexArray(VAO)

    VBO = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, VBO)
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.ptr, GL_STATIC_DRAW)

    # position attribute (location=0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), None)
    glEnableVertexAttribArray(0)

    # color attribute (location=1)
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), ctypes.c_void_p(3*glm.sizeof(glm.float32)))
    glEnableVertexAttribArray(1)

    return VAO

def prepare_vao_pivot():
    vertices = glm.array(glm.float32,
        0.0, 0.0, 0.0,  1.0, 1.0, 1.0,  # 원점, 흰색
    )

    VAO = glGenVertexArrays(1)
    glBindVertexArray(VAO)

    VBO = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, VBO)
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.ptr, GL_STATIC_DRAW)

    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), None)
    glEnableVertexAttribArray(0)

    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), ctypes.c_void_p(3*glm.sizeof(glm.float32)))
    glEnableVertexAttribArray(1)

    return VAO

def prepare_vao_cube_():
    # prepare vertex data (in main memory)
    # 36 vertices for 12 triangles
    vertices = glm.array(glm.float32,
        # position            color
        -0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v0
         0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v2
         0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v1

        -0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v0
        -0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v3
         0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v2

        -0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v4
         0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v5
         0.5 , -0.5 , -0.5 ,  1, 1, 1, # v6

        -0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v4
         0.5 , -0.5 , -0.5 ,  1, 1, 1, # v6
        -0.5 , -0.5 , -0.5 ,  1, 1, 1, # v7

        -0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v0
         0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v1
         0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v5

        -0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v0
         0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v5
        -0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v4

        -0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v3
         0.5 , -0.5 , -0.5 ,  1, 1, 1, # v6
         0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v2

        -0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v3
        -0.5 , -0.5 , -0.5 ,  1, 1, 1, # v7
         0.5 , -0.5 , -0.5 ,  1, 1, 1, # v6

         0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v1
         0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v2
         0.5 , -0.5 , -0.5 ,  1, 1, 1, # v6

         0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v1
         0.5 , -0.5 , -0.5 ,  1, 1, 1, # v6
         0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v5

        -0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v0
        -0.5 , -0.5 , -0.5 ,  1, 1, 1, # v7
        -0.5 , -0.5 ,  0.5 ,  1, 1, 1, # v3

        -0.5 ,  0.5 ,  0.5 ,  1, 1, 1, # v0
        -0.5 ,  0.5 , -0.5 ,  1, 1, 1, # v4
        -0.5 , -0.5 , -0.5 ,  1, 1, 1, # v7
    )

    VAO = glGenVertexArrays(1)
    glBindVertexArray(VAO)

    VBO = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, VBO)
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.ptr, GL_STATIC_DRAW)

    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), None)
    glEnableVertexAttribArray(0)

    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), ctypes.c_void_p(3 * glm.sizeof(glm.float32)))
    glEnableVertexAttribArray(1)

    return VAO

def prepare_vao_grid(grid_size=10):
    grid_vertices = []

    # x축 방향 선 (z값마다 x방향으로 뻗는 선) - 빨간색
    for z in range(-grid_size, grid_size + 1):
        grid_vertices += [-grid_size, 0.0, float(z),  1.0, 0.0, 0.0]
        grid_vertices += [ grid_size, 0.0, float(z),  1.0, 0.0, 0.0]

    # z축 방향 선 (x값마다 z방향으로 뻗는 선) - 파란색
    for x in range(-grid_size, grid_size + 1):
        grid_vertices += [float(x), 0.0, -grid_size,  0.0, 0.0, 1.0]
        grid_vertices += [float(x), 0.0,  grid_size,  0.0, 0.0, 1.0]

    vertices = glm.array(glm.float32, *grid_vertices)
    vertex_count = (2 * grid_size + 1) * 2 * 2  # 각 방향 선 수 * 2축 * 2정점

    VAO = glGenVertexArrays(1)
    glBindVertexArray(VAO)

    VBO = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, VBO)
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.ptr, GL_STATIC_DRAW)

    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), None)
    glEnableVertexAttribArray(0)

    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), ctypes.c_void_p(3 * glm.sizeof(glm.float32)))
    glEnableVertexAttribArray(1)

    return VAO, vertex_count

def prepare_vao_frame():
    # prepare vertex data (in main memory)
    vertices = glm.array(glm.float32,
        # position        # color
         0.0, 0.0, 0.0,  1.0, 0.0, 0.0, # x-axis start
         5.0, 0.0, 0.0,  1.0, 0.0, 0.0, # x-axis end
         0.0, 0.0, 0.0,  0.0, 1.0, 0.0, # y-axis start
         0.0, 5.0, 0.0,  0.0, 1.0, 0.0, # y-axis end
         0.0, 0.0, 0.0,  0.0, 0.0, 1.0, # z-axis start
         0.0, 0.0, 5.0,  0.0, 0.0, 1.0, # z-axis end
    )

    # create and activate VAO (vertex array object)
    VAO = glGenVertexArrays(1)  # create a vertex array object ID and store it to VAO variable
    glBindVertexArray(VAO)      # activate VAO

    # create and activate VBO (vertex buffer object)
    VBO = glGenBuffers(1)   # create a buffer object ID and store it to VBO variable
    glBindBuffer(GL_ARRAY_BUFFER, VBO)  # activate VBO as a vertex buffer object

    # copy vertex data to VBO
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.ptr, GL_STATIC_DRAW)

    # configure vertex positions
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), None)
    glEnableVertexAttribArray(0)

    # configure vertex colors
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * glm.sizeof(glm.float32), ctypes.c_void_p(3*glm.sizeof(glm.float32)))
    glEnableVertexAttribArray(1)

    return VAO
