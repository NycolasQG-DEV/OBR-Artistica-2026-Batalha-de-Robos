# visuals/sky.py — esfera de skybox procedural
import math
from panda3d.core import (
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles,
)


def create_sky_sphere(radius: float = 1.0, segments: int = 32, rings: int = 16) -> Geom:
    format = GeomVertexFormat.getV3n3t2()
    vdata = GeomVertexData("sphere", format, Geom.UHStatic)
    
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")
    
    for r in range(rings + 1):
        theta = r * math.pi / rings
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        
        for s in range(segments + 1):
            phi = s * 2 * math.pi / segments
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)
            
            x = sin_theta * cos_phi
            y = sin_theta * sin_phi
            z = cos_theta
            
            vertex.addData3(x * radius, y * radius, z * radius)
            normal.addData3(x, y, z)
            texcoord.addData2(1.0 - (s / segments), r / rings)
            
    geom = Geom(vdata)
    
    for r in range(rings):
        for s in range(segments):
            v00 = r * (segments + 1) + s
            v01 = r * (segments + 1) + s + 1
            v10 = (r + 1) * (segments + 1) + s
            v11 = (r + 1) * (segments + 1) + s + 1
            
            tris = GeomTriangles(Geom.UHStatic)
            tris.addVertex(v00)
            tris.addVertex(v01)
            tris.addVertex(v10)
            geom.addPrimitive(tris)
            
            tris = GeomTriangles(Geom.UHStatic)
            tris.addVertex(v01)
            tris.addVertex(v11)
            tris.addVertex(v10)
            geom.addPrimitive(tris)
            
    return geom
