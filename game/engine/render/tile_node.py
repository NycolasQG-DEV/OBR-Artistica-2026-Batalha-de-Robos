# visuals/tile_node.py — representação visual de um tile do grid
import os
import time
import math
from panda3d.core import LColor, GeomNode, Texture
from settings import TILE_SIZE, TILE_SCALE, TILE_HEIGHT, C_TILE, C_TILE_H
from engine.render.geometry import lc, grid_to_world, create_clean_cube


class TileNode:
    def __init__(self, render, loader, col: int, row: int):
        self.col = col
        self.row = row
        pos = grid_to_world(col, row)

        tile_w = TILE_SIZE * TILE_SCALE
        tile_geom = create_clean_cube(tile_w, tile_w, TILE_HEIGHT)
        tile_geom_node = GeomNode(f"tile_geom_{col}_{row}")
        tile_geom_node.addGeom(tile_geom)
        self.node = render.attachNewNode(tile_geom_node)
        self.node.setPos(pos.getX(), pos.getY(), -TILE_HEIGHT / 2)
        
        self.has_texture = False
        tile_tex_path = "assets/textures/tile.png"
        if os.path.exists(tile_tex_path):
            try:
                tile_tex = loader.loadTexture(tile_tex_path)
                if tile_tex:
                    tile_tex.setMinfilter(Texture.FTLinearMipmapLinear)
                    tile_tex.setMagfilter(Texture.FTLinear)
                    self.node.setTexture(tile_tex, 1)
                    self.node.setShaderAuto()
                    self.node.setColor(LColor(1.0, 1.0, 1.0, 1.0))
                    self.has_texture = True
            except Exception as e:
                print(f"[TileNode] Erro ao carregar textura {tile_tex_path}: {e}")

        if not self.has_texture:
            self.node.setColor(LColor(0.18, 0.2, 0.28, 1))
            self.node.clearTexture()
            self.node.setMaterialOff(1)
            self.node.setShaderOff(1)
            
        self._base_color = C_TILE
        self._highlighted = False
        self._warning = False
        self._update_color()

    def set_highlight(self, hl: bool):
        self._highlighted = hl
        self._update_color()

    def set_warning(self, warn: bool):
        self._warning = warn
        self._update_color()

    def _update_color(self):
        # The user requested no tile darkening effects, so we leave it constant
        if self.has_texture:
            self.node.setColor(LColor(1.0, 1.0, 1.0, 1.0))
        else:
            self.node.setColor(lc(*C_TILE))

    def pulse(self, dt: float):
        pass # The user requested to remove tile coloring effects
