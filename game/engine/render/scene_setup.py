# engine/render/scene_setup.py — configuração de iluminação e atualização da skybox
from panda3d.core import AmbientLight, DirectionalLight, PointLight, LColor

def setup_lights(app):
    # Ambiente
    al = AmbientLight("ambient")
    al.setColor(LColor(0.25, 0.25, 0.35, 1))
    app.render.setLight(app.render.attachNewNode(al))

    # Direcional principal (sol)
    dl = DirectionalLight("directional")
    dl.setColor(LColor(0.9, 0.85, 0.8, 1))
    dln = app.render.attachNewNode(dl)
    dln.setHpr(45, -60, 0)
    app.render.setLight(dln)

    # Ponto de luz na arena
    pl = PointLight("arena_light")
    pl.setColor(LColor(0.4, 0.5, 1.0, 1))
    pl.setAttenuation((1, 0.05, 0.01))
    pln = app.render.attachNewNode(pl)
    pln.setPos(0, 0, 8)
    app.render.setLight(pln)

def update_skybox(app, task):
    if hasattr(app, "skybox") and app.skybox and not app.skybox.isEmpty():
        app.skybox.setPos(app.camera.getPos(app.render))
    return task.cont
