# Purpose: setup initial viewport for a DXF drawing
# Copyright (c) 2016-2021 Manfred Moitzi
# License: MIT License
import pathlib
import ezdxf

DIR = pathlib.Path("~/Desktop/Outbox").expanduser()
FILENAME = "page_setup_R12.dxf"


def draw_raster(doc):
    marker = doc.blocks.new(name="MARKER")
    attribs = {"color": 2}
    marker.add_line((-1, 0), (1, 0), dxfattribs=attribs)
    marker.add_line((0, -1), (0, 1), dxfattribs=attribs)
    marker.add_circle((0, 0), 0.4, dxfattribs=attribs)

    marker.add_attdef(
        "XPOS", (0.5, -1.0), dxfattribs={"height": 0.25, "color": 4}
    )
    marker.add_attdef(
        "YPOS", (0.5, -1.5), dxfattribs={"height": 0.25, "color": 4}
    )
    modelspace = doc.modelspace()
    for x in range(10):
        for y in range(10):
            xcoord = x * 10
            ycoord = y * 10
            values = {
                "XPOS": f"x = {xcoord}",
                "YPOS": f"y = {ycoord}",
            }
            modelspace.add_auto_blockref("MARKER", (xcoord, ycoord), values)


def setup_active_viewport(doc):
    # delete '*Active' viewport configuration
    doc.viewports.delete_config("*ACTIVE")
    # the available display area in AutoCAD has the virtual lower-left
    # corner (0, 0) and the virtual upper-right corner (1, 1)

    # first viewport, uses the left half of the screen
    viewport = doc.viewports.new("*ACTIVE")
    viewport.dxf.lower_left = (0, 0)
    viewport.dxf.upper_right = (0.5, 1)

    # target point defines the origin of the DCS, this is the default value
    viewport.dxf.target = (0, 0, 0)

    # move this location (in DCS) to the center of the viewport
    viewport.dxf.center = (40, 30)

    # height of viewport in drawing units, this parameter works
    viewport.dxf.height = 15
    viewport.dxf.aspect_ratio = 1.0  # aspect ratio of viewport (x/y)

    # second viewport, uses the right half of the screen
    viewport = doc.viewports.new("*ACTIVE")
    viewport.dxf.lower_left = (0.5, 0)
    viewport.dxf.upper_right = (1, 1)

    # target point defines the origin of the DCS
    viewport.dxf.target = (60, 20, 0)

    # move this location (in DCS, model space = 60, 20) to the center of the viewport
    viewport.dxf.center = (0, 0)

    # height of viewport in drawing units, this parameter works
    viewport.dxf.height = 15

    # aspect ratio of viewport (x/y)
    viewport.dxf.aspect_ratio = 2.0


def layout_page_setup(doc):
    # DXF R12 supports just one paper space layout
    layout = doc.layout()
    layout.page_setup(size=(11, 8.5), margins=(1, 2, 1, 2), units="inch")
    lower_left, upper_right = layout.get_paper_limits()
    x1, y1 = lower_left
    x2, y2 = upper_right
    center = lower_left.lerp(upper_right)
    layout.add_line((x1, center.y), (x2, center.y))  # horizontal center line
    layout.add_line((center.x, y1), (center.x, y2))  # vertical center line
    layout.add_circle((0, 0), radius=0.1)  # plot origin


if __name__ == "__main__":
    doc = ezdxf.new("R12")
    draw_raster(doc)
    setup_active_viewport(doc)
    layout_page_setup(doc)
    doc.saveas(DIR / FILENAME)
    print(f'DXF file "{FILENAME}" created.')
