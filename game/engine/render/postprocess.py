# engine/render/postprocess.py — shader e quad de renderização de dither PSX retro
from direct.filter.FilterManager import FilterManager
from panda3d.core import Texture, Shader, Vec2

def setup_dither_postprocess(app):
    try:
        app.filter_manager = FilterManager(app.win, app.cam)
        app.scene_tex = Texture()
        app.dither_quad = app.filter_manager.renderSceneInto(colortex=app.scene_tex)
        
        if app.dither_quad:
            vert_code = """#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 texcoord;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    texcoord = p3d_MultiTexCoord0;
}
"""
            frag_code = """#version 150
uniform sampler2D scene_tex;
in vec2 texcoord;
out vec4 p3d_FragColor;
uniform vec2 win_size;

const float bayerMatrix[16] = float[16](
     0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
    12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
     3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
    15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
);

const vec3 palette[16] = vec3[16](
    vec3(0.102, 0.110, 0.173),
    vec3(0.365, 0.153, 0.365),
    vec3(0.694, 0.243, 0.325),
    vec3(0.937, 0.490, 0.341),
    vec3(1.000, 0.804, 0.459),
    vec3(0.655, 0.941, 0.439),
    vec3(0.220, 0.718, 0.392),
    vec3(0.145, 0.443, 0.475),
    vec3(0.161, 0.212, 0.435),
    vec3(0.231, 0.365, 0.788),
    vec3(0.255, 0.651, 0.965),
    vec3(0.451, 0.937, 0.969),
    vec3(0.957, 0.957, 0.957),
    vec3(0.580, 0.690, 0.761),
    vec3(0.337, 0.424, 0.525),
    vec3(0.200, 0.235, 0.341)
);

void findClosestColors(vec3 color, out vec3 first, out vec3 second, out float factor) {
    float firstDist = 9999.0;
    float secondDist = 9999.0;
    int firstIdx = 0;
    int secondIdx = 0;
    
    for(int i = 0; i < 16; i++) {
        float dist = distance(color, palette[i]);
        if(dist < firstDist) {
            secondDist = firstDist;
            secondIdx = firstIdx;
            
            firstDist = dist;
            firstIdx = i;
        } else if(dist < secondDist) {
            secondDist = dist;
            secondIdx = i;
        }
    }
    
    first = palette[firstIdx];
    second = palette[secondIdx];
    
    float totalDist = firstDist + secondDist;
    if(totalDist > 0.0) {
        factor = firstDist / totalDist;
    } else {
        factor = 0.0;
    }
}

void main() {
    float targetHeight = 280.0;
    float aspect = win_size.x / win_size.y;
    vec2 targetRes = vec2(targetHeight * aspect, targetHeight);
    
    vec2 uv = floor(texcoord * targetRes) / targetRes;
    vec4 color = texture(scene_tex, uv);
    
    ivec2 coord = ivec2(gl_FragCoord.xy);
    int x = coord.x % 4;
    int y = coord.y % 4;
    float ditherValue = bayerMatrix[y * 4 + x];
    
    vec3 c1, c2;
    float factor;
    findClosestColors(color.rgb, c1, c2, factor);
    
    vec3 finalColor = (ditherValue < factor) ? c2 : c1;
    p3d_FragColor = vec4(finalColor, 1.0);
}
"""
            shader = Shader.make(Shader.SL_GLSL, vert_code, frag_code)
            app.dither_quad.setShader(shader)
            app.dither_quad.setShaderInput("scene_tex", app.scene_tex)
            
            sw = app.win.getXSize()
            sh = app.win.getYSize()
            app.dither_quad.setShaderInput("win_size", Vec2(sw, sh))
            print("[RobotArena3D] Pipeline de Dithering PSX (Sweetie 16 - 280p) ativado com sucesso.")
        else:
            print("[RobotArena3D] Erro: FilterManager nao conseguiu criar o quad de render.")
    except Exception as e:
        print(f"[RobotArena3D] Falha catastrófica ao iniciar o shader de dithering: {e}")
