# Copyright (c) 2022, Manfred Moitzi
# License: MIT License

from pathlib import Path
import math
import ezdxf

from ezdxf.render.forms import torus

DIR = Path("~/Desktop/Outbox").expanduser()
if not DIR.exists():
    DIR = Path(".")

doc = ezdxf.new()
doc.layers.new("form", dxfattribs={"color": 2})
normals_layer = doc.layers.new("normals", dxfattribs={"color": 6})
normals_layer.off()
msp = doc.modelspace()

closed_torus = torus(major_count=32, minor_count=16)
closed_torus.render_mesh(msp, dxfattribs={"layer": "form"})
closed_torus.render_normals(msp, dxfattribs={"layer": "normals"})

open_torus = torus(major_count=16, minor_count=16, end_angle=math.pi, caps=True)
open_torus.translate(5)
open_torus.render_mesh(msp, dxfattribs={"layer": "form"})
open_torus.render_normals(msp, dxfattribs={"layer": "normals"})

closed_tri_torus = torus(major_count=32, minor_count=16, ngons=False)
closed_tri_torus.translate(0, 5)
closed_tri_torus.render_mesh(msp, dxfattribs={"layer": "form"})
closed_tri_torus.render_normals(msp, dxfattribs={"layer": "normals"})

open_tri_torus = torus(
    major_count=16, minor_count=16, end_angle=math.pi, caps=True, ngons=False
)
open_tri_torus.translate(5, 5)
open_tri_torus.render_mesh(msp, dxfattribs={"layer": "form"})
open_tri_torus.render_normals(msp, dxfattribs={"layer": "normals"})

doc.set_modelspace_vport(7, center=(2.5, 2.5))
doc.saveas(DIR / "torus.dxf")
