from OpenGL.GL import *

# ──────────────────────────────────────────────────────────────────────
# Unlit (flat-color) 셰이더 — grid / frame / pivot 등 보조 요소용
#   layout: vec3 position, vec3 color
# ──────────────────────────────────────────────────────────────────────

g_vertex_shader_src = '''
#version 330 core

layout (location = 0) in vec3 vin_pos;
layout (location = 1) in vec3 vin_color;

out vec4 vout_color;

uniform mat4 MVP;

void main()
{
    // 3D points in homogeneous coordinates
    vec4 p3D_in_hcoord = vec4(vin_pos.xyz, 1.0);

    gl_Position = MVP * p3D_in_hcoord;

    vout_color = vec4(vin_color, 1.);
}
'''

g_fragment_shader_src = '''
#version 330 core

in vec4 vout_color;

out vec4 FragColor;

void main()
{
    FragColor = vout_color;
}
'''


# ──────────────────────────────────────────────────────────────────────
# Phong illumination + Phong shading 셰이더 — OBJ 메시 렌더링용
#   layout: vec3 position, vec3 normal
#
#   - Phong shading: fragment 단계에서 법선을 normalize 해 픽셀마다
#     라이팅을 계산 (Gouraud처럼 정점에서 lit 계산하지 않음)
#   - NormalMatrix = transpose(inverse(mat3(M))) 로 비균일 스케일에서도
#     normal이 깨지지 않도록 함
#   - 단일 점광원 + ambient/diffuse/specular 분리
# ──────────────────────────────────────────────────────────────────────

g_vertex_shader_phong = '''
#version 330 core

layout (location = 0) in vec3 vin_pos;
layout (location = 1) in vec3 vin_normal;

out vec3 vout_world_pos;
out vec3 vout_normal;

uniform mat4 MVP;
uniform mat4 M;
uniform mat3 NormalMatrix;

void main()
{
    vec4 world_pos = M * vec4(vin_pos, 1.0);
    vout_world_pos = vec3(world_pos);
    vout_normal    = NormalMatrix * vin_normal;

    gl_Position = MVP * vec4(vin_pos, 1.0);
}
'''

g_fragment_shader_phong = '''
#version 330 core

in vec3 vout_world_pos;
in vec3 vout_normal;

out vec4 FragColor;

uniform vec3  view_pos;        // 카메라 world 위치 (specular용)
uniform vec3  light_pos;       // 광원 world 위치
uniform vec3  light_color;     // 광원 색

uniform vec3  material_color;  // 베이스 디퓨즈/앰비언트 색
uniform float shininess;       // specular 광택도
uniform float ka;              // ambient 계수
uniform float kd;              // diffuse 계수
uniform float ks;              // specular 계수

void main()
{
    // fragment 단위로 정규화 (Phong shading의 핵심)
    vec3 N = normalize(vout_normal);
    vec3 L = normalize(light_pos - vout_world_pos);
    vec3 V = normalize(view_pos  - vout_world_pos);
    vec3 R = reflect(-L, N);

    // ambient
    vec3 ambient = ka * light_color * material_color;

    // diffuse (Lambert)
    float diff   = max(dot(N, L), 0.0);
    vec3 diffuse = kd * diff * light_color * material_color;

    // specular (Phong reflection model)
    float spec    = pow(max(dot(R, V), 0.0), shininess);
    // 빛이 뒷면에서 오면 specular 제거 (light leak 방지)
    if (diff <= 0.0) spec = 0.0;
    vec3 specular = ks * spec * light_color;

    FragColor = vec4(ambient + diffuse + specular, 1.0);
}
'''

def load_shaders(vertex_shader_source, fragment_shader_source):
    # build and compile our shader program
    # ------------------------------------

    # vertex shader
    vertex_shader = glCreateShader(GL_VERTEX_SHADER)    # create an empty shader object
    glShaderSource(vertex_shader, vertex_shader_source) # provide shader source code
    glCompileShader(vertex_shader)                      # compile the shader object

    # check for shader compile errors
    success = glGetShaderiv(vertex_shader, GL_COMPILE_STATUS)
    if (not success):
        infoLog = glGetShaderInfoLog(vertex_shader)
        print("ERROR::SHADER::VERTEX::COMPILATION_FAILED\n" + infoLog.decode())

    # fragment shader
    fragment_shader = glCreateShader(GL_FRAGMENT_SHADER)    # create an empty shader object
    glShaderSource(fragment_shader, fragment_shader_source) # provide shader source code
    glCompileShader(fragment_shader)                        # compile the shader object

    # check for shader compile errors
    success = glGetShaderiv(fragment_shader, GL_COMPILE_STATUS)
    if (not success):
        infoLog = glGetShaderInfoLog(fragment_shader)
        print("ERROR::SHADER::FRAGMENT::COMPILATION_FAILED\n" + infoLog.decode())

    # link shaders
    shader_program = glCreateProgram()               # create an empty program object
    glAttachShader(shader_program, vertex_shader)    # attach the shader objects to the program object
    glAttachShader(shader_program, fragment_shader)
    glLinkProgram(shader_program)                    # link the program object

    # check for linking errors
    success = glGetProgramiv(shader_program, GL_LINK_STATUS)
    if (not success):
        infoLog = glGetProgramInfoLog(shader_program)
        print("ERROR::SHADER::PROGRAM::LINKING_FAILED\n" + infoLog.decode())

    glDeleteShader(vertex_shader)
    glDeleteShader(fragment_shader)

    return shader_program    # return the shader program
