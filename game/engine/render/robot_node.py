# visuals/robot_node.py — representação visual 3D de um robô
import os
import json
import math

from panda3d.core import LColor, CardMaker, TransparencyAttrib, TextureAttrib, Texture

from settings import ROBOT_BOX_SCALE, BOSS_SCALE
from engine.render.geometry import lc, grid_to_world


class RobotNode:
    def __init__(self, render, robot_data, loader):
        self.data  = robot_data
        self._base_z = 0.0

        # Define a escala dependendo se é o jogador ou o Boss gigante
        if robot_data.is_player:
            self.scale = ROBOT_BOX_SCALE
        else:
            self.scale = BOSS_SCALE

        # Cubo principal
        self.root = render.attachNewNode(f"robot_{robot_data.name_code}")

        # Corpo (Tenta carregar o modelo personalizado em assets/models)
        self.is_custom_model = False
        self.body = None

        # 1. Determina o nome base e o caminho da configuração
        robot_name = robot_data.name_code.lower()
        if robot_data.is_player:
            config_path = f"assets/models/{robot_name}.json"
        else:
            config_path = f"assets/models/{robot_name}_boss.json"
            if not os.path.exists(config_path):
                config_path = f"assets/models/{robot_name}.json"
            if not os.path.exists(config_path):
                config_path = "assets/models/boss.json"

        # 2. Carrega as configurações do JSON
        model_config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    model_config = json.load(f)
            except Exception as e:
                print(f"[RobotNode] Erro ao ler configuração {config_path}: {e}")

        # Extrai os parâmetros
        model_file = model_config.get("model_file", "")
        texture_file = model_config.get("texture_file", "")
        scale_val = model_config.get("scale", 1.0)
        self.scale_mult = scale_val
        
        rotation_val = model_config.get("rotation", [0.0, 0.0, 0.0])
        offset_val = model_config.get("offset", [0.0, 0.0, 0.0])
        pivot_offset = model_config.get("pivot_offset", [0.0, 0.0, 0.0])
        rendering_config = model_config.get("rendering", {})
        
        # 3. Localiza o arquivo de modelo 3D
        custom_path = None
        if model_file:
            path = model_file
            if not os.path.isabs(path) and not os.path.exists(path):
                path = os.path.join("assets/models", model_file)
            if os.path.exists(path):
                custom_path = path
        
        # Se não especificou ou não achou o arquivo de modelo, tenta achar um fallback com o nome do robô
        if not custom_path:
            extensions = [".egg", ".bam", ".obj", ".fbx", ".glb", ".gltf"]
            fallback_base = robot_name
            for ext in extensions:
                path = f"assets/models/{fallback_base}{ext}"
                if os.path.exists(path):
                    custom_path = path
                    break

        # 4. Carrega o modelo
        is_obj = False
        if custom_path:
            try:
                from panda3d.core import Filename
                abs_path = os.path.abspath(custom_path)
                unix_path = Filename.fromOsSpecific(abs_path).getFullpath()
                self.body = loader.loadModel(unix_path)
                if self.body and not self.body.isEmpty():
                    self.is_custom_model = True
                    if custom_path.lower().endswith(".obj"):
                        is_obj = True
                        mtl_path = os.path.splitext(custom_path)[0] + ".mtl"
                        if os.path.exists(mtl_path):
                            print(f"[RobotNode] Identificado arquivo MTL associado: {mtl_path}")
                        else:
                            print(f"[RobotNode] Arquivo MTL nao encontrado para o modelo: {custom_path}")
            except Exception as e:
                print(f"[RobotNode] Falha ao carregar modelo {custom_path}: {e}")
                self.body = None

        if not self.is_custom_model or self.body is None or self.body.isEmpty():
            self.pivot = self.root
            self.body = loader.loadModel("models/misc/rgbCube")
            if self.body is None or self.body.isEmpty():
                # Fallback: criar geometria simples com CardMaker
                self.body = self._make_box(render, robot_data.base_color)
            else:
                self.body.setColor(lc(*robot_data.base_color))
                self.body.setScale(*self.scale)
            self.body.reparentTo(self.root)
        else:
            # Se carregou com sucesso o modelo customizado, define a escala com base no JSON
            if isinstance(scale_val, (list, tuple)):
                self.scale = (scale_val[0], scale_val[1], scale_val[2])
            else:
                self.scale = (scale_val, scale_val, scale_val)

            self.pivot = self.root.attachNewNode(f"pivot_{robot_name}")
            self.pivot.setPos(offset_val[0], offset_val[1], offset_val[2])
            self.pivot.setHpr(rotation_val[0], rotation_val[1], rotation_val[2])
            
            self.body.reparentTo(self.pivot)
            self.body.setPos(-pivot_offset[0], -pivot_offset[1], -pivot_offset[2])
            self.body.setScale(*self.scale)
            self.body.setShaderAuto()
            
            use_native = model_config.get("use_native_materials", False)
            
            if not is_obj and not use_native:
                self.body.setMaterialOff(1) # Disable default PBR materials which override custom textures/colors
            
            # Verifica se possui textura nativa
            self.has_default_texture = False
            if self.body.findTexture("*") or (is_obj and self.body.findAllMaterials().getNumMaterials() > 0) or use_native:
                self.has_default_texture = True
                print(f"[RobotNode] Modelo carregado com textura/materiais nativos.")
            
            # Aplica textura de override se definida
            self.has_override_texture = False
            if texture_file and not is_obj and not use_native:
                tex_path = texture_file
                if not os.path.isabs(tex_path) and not os.path.exists(tex_path):
                    tex_path = os.path.join("assets/models", texture_file)
                if not os.path.isabs(tex_path) and not os.path.exists(tex_path):
                    tex_path = os.path.join("assets/textures", texture_file)
                
                # Normaliza barras para o VFS do Panda3D
                tex_path = tex_path.replace("\\", "/")
                
                if os.path.exists(tex_path):
                    try:
                        from panda3d.core import Filename
                        abs_tex_path = os.path.abspath(tex_path)
                        unix_tex_path = Filename.fromOsSpecific(abs_tex_path).getFullpath()
                        tex = loader.loadTexture(unix_tex_path)
                        if tex:
                            self.body.setTexture(tex, 1)
                            self.has_override_texture = True
                            print(f"[RobotNode] Textura personalizada aplicada: {unix_tex_path}")
                    except Exception as e:
                        print(f"[RobotNode] Erro ao carregar textura {tex_path}: {e}")
                else:
                    print(f"[RobotNode] Textura de override não encontrada: {texture_file} (tentado em models e textures)")

            # Aplica Shader personalizado de override se definido em rendering
            shader_vert = rendering_config.get("shader_vertex", "")
            shader_frag = rendering_config.get("shader_fragment", "")
            if shader_vert or shader_frag:
                vert_path = shader_vert
                if vert_path and not os.path.isabs(vert_path) and not os.path.exists(vert_path):
                    vert_path = os.path.join("assets/models", shader_vert)
                
                frag_path = shader_frag
                if frag_path and not os.path.isabs(frag_path) and not os.path.exists(frag_path):
                    frag_path = os.path.join("assets/models", shader_frag)
                
                if os.path.exists(vert_path) and os.path.exists(frag_path):
                    try:
                        from panda3d.core import Shader, Filename
                        unix_vert = Filename.fromOsSpecific(os.path.abspath(vert_path)).getFullpath()
                        unix_frag = Filename.fromOsSpecific(os.path.abspath(frag_path)).getFullpath()
                        custom_shader = Shader.load(Shader.SL_GLSL, unix_vert, unix_frag)
                        if custom_shader:
                            self.body.setShader(custom_shader)
                            print(f"[RobotNode] Shader personalizado aplicado: vert={unix_vert}, frag={unix_frag}")
                    except Exception as e:
                        print(f"[RobotNode] Erro ao carregar shader personalizado: {e}")
                else:
                    print(f"[RobotNode] Arquivos de shader personalizado não encontrados: vert={vert_path}, frag={frag_path}")

        print(f"[RobotNode debug] name_code={robot_data.name_code} is_player={robot_data.is_player} config={config_path} model_file={model_file} custom_path={custom_path} is_custom={self.is_custom_model} scale_mult={self.scale_mult}")

        # Indicador desativado (removido a pedido)
        self.indicator = None

        # Sombra no chão (círculo achatado)
        shadow = loader.loadModel("models/misc/rgbCube")
        if shadow and not shadow.isEmpty():
            shadow.setColor(LColor(0, 0, 0, 0.35))
            shadow.setScale(self.scale[0] * 0.9, self.scale[1] * 0.9, 0.04 * self.scale[2])
            if self.is_custom_model:
                # Sombra fica exatamente no chão (z = 0.01 para evitar z-fighting)
                shadow.setPos(0, 0, 0.01)
            else:
                shadow.setPos(0, 0, -self.scale[2] * 0.52)
            shadow.reparentTo(self.root)
            shadow.setTransparency(TransparencyAttrib.MAlpha)

        # self.root.setTransparency(TransparencyAttrib.MAlpha)  # Removido para evitar invisibilidade da textura do boss
        self._update_position()
        self._time = 0.0

    def _make_box(self, render, color):
        """Fallback: usa a primitiva embutida."""
        node = render.attachNewNode("box_fallback")
        cm = CardMaker("face")
        w, h, d = self.scale
        verts = [
            # frente/trás
            [(-w/2,-d/2,-h/2),(w/2,-d/2,-h/2),(w/2,-d/2,h/2),(-w/2,-d/2,h/2)],
            [(-w/2, d/2,-h/2),(w/2, d/2,-h/2),(w/2, d/2,h/2),(-w/2, d/2,h/2)],
        ]
        return node

    def _update_position(self):
        pos = grid_to_world(self.data.v_tx, self.data.v_ty)
        if self.is_custom_model:
            self.root.setPos(pos.getX(), pos.getY(), pos.getZ())
        else:
            self.root.setPos(pos.getX(), pos.getY(), pos.getZ() + self.scale[2] / 2)

    def update(self, dt: float):
        self._time += dt
        self._update_position()

        # Sem bob — robô fica no chão na altura correspondente à sua escala Z
        if self.is_custom_model:
            pos = grid_to_world(self.data.v_tx, self.data.v_ty)
            self.root.setZ(pos.getZ())
        else:
            self.root.setZ(self.scale[2] / 2)

        # Rotação durante spin
        if self.data._spin_active:
            # v_h is already updated smoothly by robot.turn, so we follow it directly to avoid double-spin
            self.root.setH(self.data.v_h)
        else:
            # Suavemente segue o heading lógico
            self.root.setH(self.data.v_h)

        # Flash ao tomar dano / capturar powerup
        if self.data.flash_timer > 0:
            self.body.setColorScale(LColor(2.5, 2.5, 2.5, 1.0))
        else:
            self.body.setColorScale(LColor(1.0, 1.0, 1.0, 1.0))
            # Efeito de defesa ou cor normal
            # Efeito de defesa ou cor normal
            r, g, b, a = (1.0, 1.0, 1.0, 1.0) if (self.is_custom_model and (self.has_override_texture or self.has_default_texture)) else self.data.base_color
            if self.data.is_defending:
                pulse = 0.7 + 0.3 * math.sin(self._time * 4)
                self.body.setColor(LColor(r * 0.3, g * 0.3, min(1.0, b + 0.4 * pulse), 1.0))
            else:
                if self.is_custom_model:
                    if self.has_override_texture or self.has_default_texture:
                        self.body.setColor(LColor(1.0, 1.0, 1.0, 1.0))
                    else:
                        self.body.setColor(lc(*self.data.base_color))
                else:
                    self.body.setColor(lc(*self.data.base_color))
                    self.body.clearTexture()
                    self.body.setMaterialOff(1)
                    self.body.setShaderOff(1)

    def destroy(self):
        self.root.removeNode()
