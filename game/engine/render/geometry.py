# visuals/geometry.py — primitivas geométricas e helpers de cor/grid
import math
from panda3d.core import (
    LColor, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    TransparencyAttrib, NodePath,
)

from settings import GRID_COLS, GRID_ROWS, TILE_SIZE


# ══════════════════════════════════════════════════════════════════════
# Helpers de cor
# ══════════════════════════════════════════════════════════════════════

def lc(*rgba):
    """Converte tupla (r,g,b,a) 0-1 para LColor."""
    return LColor(*rgba)


def normalize_angle_deg(delta: float) -> float:
    """Normaliza um ângulo em graus para a faixa [-180, 180]."""
    while delta > 180.0:
        delta -= 360.0
    while delta < -180.0:
        delta += 360.0
    return delta


def grid_to_world(col: float, row: float) -> Point3:
    """Converte coluna/row do grid para posição 3D no mundo."""
    cx = (GRID_COLS - 1) / 2
    cy = (GRID_ROWS - 1) / 2
    x  =  (col - cx) * TILE_SIZE
    y  = -(row - cy) * TILE_SIZE
    return Point3(x, y, 0)


# ══════════════════════════════════════════════════════════════════════
# Cubo 3D com normais e UVs
# ══════════════════════════════════════════════════════════════════════

def create_clean_cube(size_x: float, size_y: float, size_z: float) -> Geom:
    format = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData("cube", format, Geom.UHStatic)
    
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")
    
    dx = size_x / 2.0
    dy = size_y / 2.0
    dz = size_z / 2.0
    
    # Top Face (Z+)
    vertex.addData3(-dx, -dy, dz); normal.addData3(0, 0, 1); texcoord.addData2(0, 0)
    vertex.addData3(dx, -dy, dz);  normal.addData3(0, 0, 1); texcoord.addData2(1, 0)
    vertex.addData3(dx, dy, dz);   normal.addData3(0, 0, 1); texcoord.addData2(1, 1)
    vertex.addData3(-dx, dy, dz);  normal.addData3(0, 0, 1); texcoord.addData2(0, 1)
    
    # Bottom Face (Z-)
    vertex.addData3(-dx, -dy, -dz); normal.addData3(0, 0, -1); texcoord.addData2(0, 0)
    vertex.addData3(dx, -dy, -dz);  normal.addData3(0, 0, -1); texcoord.addData2(1, 0)
    vertex.addData3(dx, dy, -dz);   normal.addData3(0, 0, -1); texcoord.addData2(1, 1)
    vertex.addData3(-dx, dy, -dz);  normal.addData3(0, 0, -1); texcoord.addData2(0, 1)
    
    # Front Face (Y-)
    vertex.addData3(-dx, -dy, -dz); normal.addData3(0, -1, 0); texcoord.addData2(0, 0)
    vertex.addData3(dx, -dy, -dz);  normal.addData3(0, -1, 0); texcoord.addData2(1, 0)
    vertex.addData3(dx, -dy, dz);   normal.addData3(0, -1, 0); texcoord.addData2(1, 1)
    vertex.addData3(-dx, -dy, dz);  normal.addData3(0, -1, 0); texcoord.addData2(0, 1)
    
    # Back Face (Y+)
    vertex.addData3(-dx, dy, -dz); normal.addData3(0, 1, 0); texcoord.addData2(0, 0)
    vertex.addData3(dx, dy, -dz);  normal.addData3(0, 1, 0); texcoord.addData2(1, 0)
    vertex.addData3(dx, dy, dz);   normal.addData3(0, 1, 0); texcoord.addData2(1, 1)
    vertex.addData3(-dx, dy, dz);  normal.addData3(0, 1, 0); texcoord.addData2(0, 1)
    
    # Left Face (X-)
    vertex.addData3(-dx, -dy, -dz); normal.addData3(-1, 0, 0); texcoord.addData2(0, 0)
    vertex.addData3(-dx, dy, -dz);  normal.addData3(-1, 0, 0); texcoord.addData2(1, 0)
    vertex.addData3(-dx, dy, dz);   normal.addData3(-1, 0, 0); texcoord.addData2(1, 1)
    vertex.addData3(-dx, -dy, dz);  normal.addData3(-1, 0, 0); texcoord.addData2(0, 1)
    
    # Right Face (X+)
    vertex.addData3(dx, -dy, -dz); normal.addData3(1, 0, 0); texcoord.addData2(0, 0)
    vertex.addData3(dx, dy, -dz);  normal.addData3(1, 0, 0); texcoord.addData2(1, 0)
    vertex.addData3(dx, dy, dz);   normal.addData3(1, 0, 0); texcoord.addData2(1, 1)
    vertex.addData3(dx, -dy, dz);  normal.addData3(1, 0, 0); texcoord.addData2(0, 1)
    
    geom = Geom(vdata)
    
    for i in range(6):
        base = i * 4
        tris = GeomTriangles(Geom.UHStatic)
        tris.addVertex(base)
        tris.addVertex(base + 1)
        tris.addVertex(base + 2)
        geom.addPrimitive(tris)
        
        tris = GeomTriangles(Geom.UHStatic)
        tris.addVertex(base)
        tris.addVertex(base + 2)
        tris.addVertex(base + 3)
        geom.addPrimitive(tris)
        
    return geom


# ══════════════════════════════════════════════════════════════════════
# Retângulo com cantos arredondados (aspect2d / UI)
# ══════════════════════════════════════════════════════════════════════

def _rounded_mesh(w, h, r, color, segs=12):
    """
    Gera um GeomNode de retângulo com cantos arredondados no plano XZ (aspect2d).
    Usa fan-triangulation a partir do centro.
    """
    # Perimeter vertices, CCW quando visto de -Y (câmera aspect2d)
    verts = []
    # 4 cantos: TR, TL, BL, BR
    corners = [
        ( w/2 - r,  h/2 - r, 0.0),
        (-w/2 + r,  h/2 - r, math.pi / 2),
        (-w/2 + r, -h/2 + r, math.pi),
        ( w/2 - r, -h/2 + r, math.pi * 1.5),
    ]
    for cx, cz, start in corners:
        for i in range(segs + 1):
            a = start + (math.pi / 2) * i / segs
            verts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    n = len(verts)

    fmt   = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("rr", fmt, Geom.UHStatic)
    vdata.setNumRows(n + 1)

    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")

    rr, rg, rb, ra = color
    # vértice central
    vw.addData3(0, 0, 0)
    cw.addData4(rr, rg, rb, ra)
    # borda
    for x, z in verts:
        vw.addData3(x, 0, z)
        cw.addData4(rr, rg, rb, ra)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(n):
        tris.addVertices(0, 1 + i, 1 + (i + 1) % n)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode("rr_mesh")
    gn.addGeom(geom)
    return gn


def make_rounded_geom(w, h, r, fill_color, border_color=None, border_thick=0.006, segs=12):
    """
    Cria um NodePath contendo a geometria de fundo de um botão ou painel arredondado.
    """
    root = NodePath("rr_geom")
    root.setTwoSided(True)
    root.setTransparency(TransparencyAttrib.MAlpha)
    
    # 1. Glow / Borda (opcional)
    if border_color:
        br = max(r, border_thick * 0.5)
        # Glow suave atrás
        gr, gg, gb, ga = border_color
        glow_color = (gr, gg, gb, ga * 0.22)
        glow_thick = border_thick * 2.0
        g_gn = _rounded_mesh(w + glow_thick * 2, h + glow_thick * 2, br + glow_thick * 0.5, glow_color, segs)
        g_np = root.attachNewNode(g_gn)
        g_np.setY(0.01)
        g_np.setBin("fixed", 19)

        # Borda rígida na frente
        b_gn = _rounded_mesh(w + border_thick * 2, h + border_thick * 2, br, border_color, segs)
        b_np = root.attachNewNode(b_gn)
        b_np.setBin("fixed", 20)

    # 2. Fill (frente)
    f_gn = _rounded_mesh(w, h, r, fill_color, segs)
    f_np = root.attachNewNode(f_gn)
    f_np.setY(-0.01)
    f_np.setBin("fixed", 21)
    
    return root


def make_rounded_panel(aspect2d, px, py, w, h, r,
                       fill_color, border_color=None,
                       border_thick=0.006, segs=12):
    """
    Cria um painel com cantos arredondados usando geometria Panda3D.
    Retorna (root_np, content_np):
      - root_np    : NodePath raiz do painel (para mover/destruir)
      - content_np : NodePath filho para parenting de labels/bars
    """
    root = aspect2d.attachNewNode("rr_panel")
    root.setPos(px, 0, py)
    root.setTwoSided(True)
    root.setTransparency(TransparencyAttrib.MAlpha)
    root.setBin("fixed", 20)

    # 1. Drop shadow (sombra preta suave e deslocada)
    shadow_color = (0.0, 0.0, 0.0, 0.40)
    shadow_thick = 0.02
    s_gn = _rounded_mesh(w + shadow_thick * 2, h + shadow_thick * 2, r + shadow_thick * 0.5, shadow_color, segs)
    s_np = root.attachNewNode(s_gn)
    s_np.setPos(0.012, 0.03, -0.012)
    s_np.setBin("fixed", 18)

    # 2. Glow Neon (brilho suave com a cor da borda)
    if border_color:
        gr, gg, gb, ga = border_color
        glow_color = (gr, gg, gb, ga * 0.15)
        glow_thick = 0.03
        g_gn = _rounded_mesh(w + glow_thick * 2, h + glow_thick * 2, r + glow_thick * 0.5, glow_color, segs)
        g_np = root.attachNewNode(g_gn)
        g_np.setY(0.01)
        g_np.setBin("fixed", 19)

    # 3. Borda (moldura rígida)
    if border_color:
        br = max(r, border_thick * 0.5)
        b_gn = _rounded_mesh(w + border_thick * 2,
                              h + border_thick * 2,
                              br, border_color, segs)
        b_np = root.attachNewNode(b_gn)
        b_np.setBin("fixed", 20)

    # 4. Fill (fundo translúcido para efeito de vidro)
    if len(fill_color) == 4:
        fr, fg, fb, fa = fill_color
        if fa == 1.0:
            fill_color = (fr, fg, fb, 0.88)
    f_gn = _rounded_mesh(w, h, r, fill_color, segs)
    f_np = root.attachNewNode(f_gn)
    f_np.setY(-0.01)   # ligeiramente à frente da borda
    f_np.setBin("fixed", 21)

    # 5. Node de conteúdo
    content = root.attachNewNode("rr_content")
    content.setY(-0.02)   # à frente de tudo
    content.setBin("fixed", 22)

    return root, content


def create_direction_arrow(length: float = 1.2, width: float = 0.6, thickness: float = 0.04) -> Geom:
    """Cria uma seta direcional estilizada (duplo chevron) como mesh 3D.
    
    A seta aponta na direção +Y (frente do robô no espaço local).
    Usa dois chevrons sobrepostos para efeito profissional.
    """
    format = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData("dir_arrow", format, Geom.UHStatic)
    
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")

    hw = width / 2.0
    dz = thickness / 2.0
    
    # Dois chevrons (>>> shape) apontando para +Y
    # Chevron 1 (traseiro)
    chevron1_verts = [
        # Ponta do chevron (centro-frente)
        (0.0, length * 0.5, dz),
        # Asa esquerda (canto externo)
        (-hw, -length * 0.1, dz),
        # Centro traseiro (recorte interior)
        (0.0, length * 0.15, dz),
        # Asa direita (canto externo)
        (hw, -length * 0.1, dz),
    ]
    
    # Chevron 2 (frontal, menor e mais à frente)
    offset_y = length * 0.35
    scale2 = 0.65
    chevron2_verts = [
        (0.0, offset_y + length * 0.5 * scale2, dz),
        (-hw * scale2, offset_y - length * 0.1 * scale2, dz),
        (0.0, offset_y + length * 0.15 * scale2, dz),
        (hw * scale2, offset_y - length * 0.1 * scale2, dz),
    ]
    
    tris = GeomTriangles(Geom.UHStatic)
    
    for chevron_verts in [chevron1_verts, chevron2_verts]:
        base_idx = vertex.getWriteRow()
        for v in chevron_verts:
            vertex.addData3(*v)
            normal.addData3(0, 0, 1)
            texcoord.addData2(v[0] / width + 0.5, v[1] / length + 0.5)
        
        # Triângulo esquerdo: ponta, asa esquerda, centro
        tris.addVertices(base_idx + 0, base_idx + 1, base_idx + 2)
        # Triângulo direito: ponta, centro, asa direita
        tris.addVertices(base_idx + 0, base_idx + 2, base_idx + 3)
        
        # Face inferior (inversão de winding para visibilidade dupla)
        base_idx2 = vertex.getWriteRow()
        for v in chevron_verts:
            vertex.addData3(v[0], v[1], -dz)
            normal.addData3(0, 0, -1)
            texcoord.addData2(v[0] / width + 0.5, v[1] / length + 0.5)
        
        tris.addVertices(base_idx2 + 0, base_idx2 + 2, base_idx2 + 1)
        tris.addVertices(base_idx2 + 0, base_idx2 + 3, base_idx2 + 2)
    
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    return geom
