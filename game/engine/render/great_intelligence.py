# engine/render/great_intelligence.py — Great Intelligence 3D Cinematic Entity
import os
import json
import math
from panda3d.core import (
    GeomNode, Geom, GeomTriangles, GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    LColor, Point3, TransparencyAttrib, Material, TexturePool
)

def create_octahedron(size_x: float, size_y: float, size_z: float) -> Geom:
    """Cria um octaedro 3D cristalino (dupla pirâmide)."""
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData("octahedron", fmt, Geom.UHStatic)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")

    hx = size_x / 2.0
    hy = size_y / 2.0
    hz = size_z / 2.0

    top    = (0, 0, hz)
    bottom = (0, 0, -hz)
    p1     = (-hx, -hy, 0)
    p2     = (hx, -hy, 0)
    p3     = (hx, hy, 0)
    p4     = (-hx, hy, 0)

    faces = [
        (top, p1, p2), (top, p2, p3), (top, p3, p4), (top, p4, p1),
        (bottom, p2, p1), (bottom, p3, p2), (bottom, p4, p3), (bottom, p1, p4)
    ]

    for v0, v1, v2 in faces:
        ax, ay, az = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
        bx, by, bz = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]
        nx = ay * bz - az * by
        ny = az * bx - ax * bz
        nz = ax * by - ay * bx
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length > 0.0001:
            nx /= length; ny /= length; nz /= length

        vertex.addData3(*v0); normal.addData3(nx, ny, nz); texcoord.addData2(0.5, 1.0)
        vertex.addData3(*v1); normal.addData3(nx, ny, nz); texcoord.addData2(0.0, 0.0)
        vertex.addData3(*v2); normal.addData3(nx, ny, nz); texcoord.addData2(1.0, 0.0)

    geom = Geom(vdata)
    tris = GeomTriangles(Geom.UHStatic)
    for i in range(8):
        base = i * 3
        tris.addVertex(base)
        tris.addVertex(base + 1)
        tris.addVertex(base + 2)
    geom.addPrimitive(tris)
    return geom


def create_ring_mesh(radius_inner: float, radius_outer: float, height: float, segments: int = 16) -> Geom:
    """Cria um anel/disco 3D em volta do núcleo."""
    fmt = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData("ring", fmt, Geom.UHStatic)

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")

    hh = height / 2.0

    for i in range(segments):
        a1 = (i / segments) * math.pi * 2.0
        a2 = ((i + 1) / segments) * math.pi * 2.0

        x1_in, y1_in = math.cos(a1) * radius_inner, math.sin(a1) * radius_inner
        x1_out, y1_out = math.cos(a1) * radius_outer, math.sin(a1) * radius_outer
        x2_in, y2_in = math.cos(a2) * radius_inner, math.sin(a2) * radius_inner
        x2_out, y2_out = math.cos(a2) * radius_outer, math.sin(a2) * radius_outer

        vertex.addData3(x1_in, y1_in, hh); normal.addData3(0, 0, 1); texcoord.addData2(0, 0)
        vertex.addData3(x1_out, y1_out, hh); normal.addData3(0, 0, 1); texcoord.addData2(1, 0)
        vertex.addData3(x2_out, y2_out, hh); normal.addData3(0, 0, 1); texcoord.addData2(1, 1)
        vertex.addData3(x2_in, y2_in, hh); normal.addData3(0, 0, 1); texcoord.addData2(0, 1)

    geom = Geom(vdata)
    for i in range(segments):
        base = i * 4
        tris1 = GeomTriangles(Geom.UHStatic)
        tris1.addVertex(base); tris1.addVertex(base + 1); tris1.addVertex(base + 2)
        geom.addPrimitive(tris1)

        tris2 = GeomTriangles(Geom.UHStatic)
        tris2.addVertex(base); tris2.addVertex(base + 2); tris2.addVertex(base + 3)
        geom.addPrimitive(tris2)

    return geom


class GreatIntelligence:
    """
    Entidade 'Great Intelligence' — Modelagem 3D única cinematográfica,
    totalmente configurável via arquivo JSON (assets/models/great_intelligence.json).
    """

    def __init__(self, app_instance, config_file: str = "assets/models/great_intelligence.json"):
        self.app = app_instance
        self.render_node = app_instance.render
        self.anim_time = 0.0
        self.config = self._load_config(config_file)

        offset = self.config.get("offset", [0.0, 5.2, 3.5])
        self.base_pos = Point3(offset[0], offset[1], offset[2])
        scale = float(self.config.get("scale", 3.5))
        hpr = self.config.get("rotation", [180.0, 0.0, 0.0])
        pivot_off = self.config.get("pivot_offset", [0.0, 0.0, 0.0])

        # Levitation params from JSON
        lev_cfg = self.config.get("levitation", {})
        self.amp_z = float(lev_cfg.get("amplitude_z", 0.45))
        self.freq_z = float(lev_cfg.get("frequency_z", 1.5))
        self.sway_x = float(lev_cfg.get("sway_x", 0.25))
        self.sway_y = float(lev_cfg.get("sway_y", 0.15))
        self.ring_spin_speed = float(lev_cfg.get("ring_spin_speed", 30.0))

        # Root Node
        self.root = self.render_node.attachNewNode("great_intelligence")
        self.root.setPos(self.base_pos)
        self.root.setScale(scale)
        self.root.setHpr(hpr[0], hpr[1], hpr[2])

        # Pivot Node
        self.pivot = self.root.attachNewNode("gi_pivot")
        self.pivot.setPos(pivot_off[0], pivot_off[1], pivot_off[2])

        self.base_hpr = [float(hpr[0]), float(hpr[1]), float(hpr[2])]

        # Animation and positioning transform overrides
        self.alpha = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        self.custom_base_pos = None

        # Tenta carregar modelo 3D externo do JSON ou usa o modelo procedural de fallback
        model_file = self.config.get("model_file", "")
        model_path = os.path.join("assets", "models", model_file) if model_file else ""
        if model_file and not os.path.exists(model_path) and os.path.exists(model_file):
            model_path = model_file

        self.external_model = None
        if model_path and os.path.exists(model_path):
            try:
                from panda3d.core import Filename
                abs_path = os.path.abspath(model_path)
                unix_path = Filename.fromOsSpecific(abs_path).getFullpath()
                print(f"[GreatIntelligence] Carregando modelo 3D GLB/BAM: {unix_path}")
                self.external_model = self.app.loader.loadModel(unix_path)
                if self.external_model:
                    self.external_model.reparentTo(self.pivot)
                    self.external_model.setShaderAuto()
                    
                    # Se o JSON tiver um arquivo de textura específico diferente das embutidas no GLB, aplica por cima
                    tex_file = self.config.get("texture_file", "")
                    tex_path = os.path.join("assets", "models", tex_file) if tex_file else ""
                    if tex_file and os.path.exists(tex_path):
                        tex = self.app.loader.loadTexture(tex_path)
                        if tex:
                            self.external_model.setTexture(tex, 1)
            except Exception as e:
                print(f"[GreatIntelligence] Erro ao carregar modelo externo {model_path}: {e}")

        # Se não houver modelo externo ou se falhar, constrói a escultura 3D procedural avançada
        if not self.external_model:
            self._build_procedural_model()

    def _load_config(self, filepath: str) -> dict:
        """Carrega as configurações do arquivo JSON."""
        default_config = {
            "model_file": "",
            "texture_file": "",
            "scale": 3.5,
            "rotation": [180.0, 0.0, 0.0],
            "offset": [0.0, 5.2, 3.5],
            "pivot_offset": [0.0, 0.0, 0.0],
            "levitation": {
                "amplitude_z": 0.45,
                "frequency_z": 1.5,
                "sway_x": 0.25,
                "sway_y": 0.15,
                "ring_spin_speed": 30.0
            },
            "rendering": {
                "color": [0.0, 0.85, 1.0, 0.92],
                "emissive_color": [0.1, 0.9, 1.0, 1.0],
                "light_off": True,
                "transparency": True
            }
        }
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_config.update(data)
                    print(f"[GreatIntelligence] Configurações JSON carregadas com sucesso de {filepath}")
            except Exception as e:
                print(f"[GreatIntelligence] Erro ao ler JSON {filepath}: {e}")
        return default_config

    def _build_procedural_model(self):
        """Constrói a escultura 3D cibernética procedural (Núcleo + Anéis Orbitais + Satélites)."""
        render_cfg = self.config.get("rendering", {})
        col = render_cfg.get("color", [0.0, 0.85, 1.0, 0.92])
        emiss = render_cfg.get("emissive_color", [0.1, 0.9, 1.0, 1.0])

        # 1. Núcleo Cristalino Central
        core_geom = create_octahedron(1.8, 1.8, 3.2)
        gnode_core = GeomNode("gi_core")
        gnode_core.addGeom(core_geom)
        self.core_node = self.pivot.attachNewNode(gnode_core)
        self.core_node.setColor(LColor(col[0], col[1], col[2], col[3]))
        if render_cfg.get("transparency", True):
            self.core_node.setTransparency(TransparencyAttrib.MAlpha)
        if render_cfg.get("light_off", True):
            self.core_node.setLightOff()

        mat_core = Material("gi_core_mat")
        mat_core.setEmission(LColor(emiss[0], emiss[1], emiss[2], emiss[3]))
        self.core_node.setMaterial(mat_core)

        # 2. Anel Orbital Interno
        ring1_geom = create_ring_mesh(1.6, 2.1, 0.2, segments=12)
        gnode_ring1 = GeomNode("gi_ring_inner")
        gnode_ring1.addGeom(ring1_geom)
        self.ring_inner_node = self.pivot.attachNewNode(gnode_ring1)
        self.ring_inner_node.setColor(LColor(0.65, 0.1, 0.95, 0.85))
        self.ring_inner_node.setTransparency(TransparencyAttrib.MAlpha)
        self.ring_inner_node.setLightOff()

        # 3. Anel Orbital Externo
        ring2_geom = create_ring_mesh(2.4, 2.9, 0.15, segments=16)
        gnode_ring2 = GeomNode("gi_ring_outer")
        gnode_ring2.addGeom(ring2_geom)
        self.ring_outer_node = self.pivot.attachNewNode(gnode_ring2)
        self.ring_outer_node.setColor(LColor(1.0, 0.65, 0.0, 0.80))
        self.ring_outer_node.setTransparency(TransparencyAttrib.MAlpha)
        self.ring_outer_node.setLightOff()

        # 4. Cristais Satélites Flutuantes
        self.satellites = []
        sat_geom = create_octahedron(0.45, 0.45, 0.9)
        for i in range(4):
            gnode_sat = GeomNode(f"gi_sat_{i}")
            gnode_sat.addGeom(sat_geom)
            sat_np = self.pivot.attachNewNode(gnode_sat)
            sat_np.setColor(LColor(0.0, 1.0, 0.6, 0.9))
            sat_np.setTransparency(TransparencyAttrib.MAlpha)
            sat_np.setLightOff()
            self.satellites.append({
                "np": sat_np,
                "angle_offset": (i / 4.0) * math.pi * 2.0,
                "radius": 3.4,
                "speed": 1.2 * (1.0 if i % 2 == 0 else -1.0)
            })

    def set_rotation_offset(self, h_offset: float = -90.0, p_offset: float = 0.0, r_offset: float = 0.0):
        """Aplica um offset de rotação (ex: -90° no Heading) em relação ao ângulo base inicial."""
        if hasattr(self, "root") and self.root:
            base = getattr(self, "base_hpr", [0.0, 90.0, 0.0])
            self.root.setHpr(base[0] + h_offset, base[1] + p_offset, base[2] + r_offset)

    def set_custom_pos(self, pos: Point3):
        self.custom_base_pos = Point3(pos.getX(), pos.getY(), pos.getZ())

    def set_alpha(self, alpha: float):
        self.alpha = max(0.0, min(1.0, alpha))
        if hasattr(self, "root") and self.root:
            self.root.setTransparency(TransparencyAttrib.MAlpha)
            self.root.setAlphaScale(self.alpha)

    def reset_transform(self):
        self.alpha = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        self.custom_base_pos = None
        self.set_alpha(1.0)
        if hasattr(self, "root") and self.root:
            base = getattr(self, "base_hpr", [0.0, 90.0, 0.0])
            self.root.setHpr(base[0], base[1], base[2])

    def update(self, dt: float):
        """Atualização de levitação no eixo Z (para cima e para baixo), sem rotação."""
        self.anim_time += dt
        t = self.anim_time

        custom_pos = getattr(self, "custom_base_pos", None)
        base = custom_pos if custom_pos is not None else self.base_pos
        off_z = getattr(self, "offset_z", 0.0)
        off_x = getattr(self, "offset_x", 0.0)
        off_y = getattr(self, "offset_y", 0.0)
        alpha = getattr(self, "alpha", 1.0)

        lev_z = base.getZ() + math.sin(t * self.freq_z) * self.amp_z + off_z
        cur_x = base.getX() + off_x
        cur_y = base.getY() + off_y

        if hasattr(self, "root") and self.root:
            self.root.setPos(cur_x, cur_y, lev_z)
            self.root.setTransparency(TransparencyAttrib.MAlpha)
            self.root.setAlphaScale(alpha)
