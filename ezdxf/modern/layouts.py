# Purpose: AC1009 layout manager
# Created: 21.03.2011
# Copyright (C) 2011, Manfred Moitzi
# License: MIT License
# The ModelSpace is a special Layout called 'Model'
from __future__ import unicode_literals
__author__ = "mozman <me@mozman.at>"

from ..entityspace import EntitySpace
from ..legacy.layouts import DXF12Layout, DXF12BlockLayout
from ..lldxf.extendedtags import ExtendedTags
from ..lldxf.const import DXFKeyError, DXFValueError, DXFTypeError, SCALE_TO_INDEX, STD_SCALES, DXFInternalEzdxfError

PAPER_SPACE = '*Paper_Space'
TMP_PAPER_SPACE_NAME = '*Paper_Space999999'
USE_STANDARD_SCALE = 16


class Layouts(object):
    def __init__(self, drawing):
        self.drawing = drawing
        self._layouts = {}  # stores Layout() objects
        self._dxf_layout_management_table = None  # stores DXF layout handles key=layout_name; value=layout_handle
        self._move_entities_section_into_blocks(drawing)
        self._setup()

    @staticmethod
    def _move_entities_section_into_blocks(drawing):
        blocks = drawing.blocks
        model_space_block = blocks.get('*MODEL_SPACE')
        model_space_block.set_entity_space(drawing.entities.model_space_entities())
        active_layout_block = blocks.get('*PAPER_SPACE')
        active_layout_block.set_entity_space(drawing.entities.active_layout_entities())
        drawing.entities.clear()  # remove entities for entities section -> stored in blocks

    @property
    def dxffactory(self):
        return self.drawing.dxffactory

    def _setup(self):
        layout_table_handle = self.drawing.rootdict['ACAD_LAYOUT']
        self._dxf_layout_management_table = self.dxffactory.wrap_handle(layout_table_handle)
        # name ... layout name
        # handle ...  handle to DXF object Layout
        for name, handle in self._dxf_layout_management_table.items():
            layout = Layout(self.drawing, handle)
            self._layouts[name] = layout

    def __len__(self):
        return len(self._layouts)

    def __contains__(self, name):
        return name in self._layouts

    def __iter__(self):
        return iter(self._layouts.values())

    def modelspace(self):
        return self.get('Model')

    def names(self):
        return self._layouts.keys()

    def get(self, name):
        if name is None:
            first_layout_name = self.names_in_taborder()[1]
            return self._layouts[first_layout_name]
        else:
            return self._layouts[name]

    def names_in_taborder(self):
        names = []
        for name, layout in self._layouts.items():
            names.append((layout.taborder, name))
        return [name for order, name in sorted(names)]

    def get_layout_for_entity(self, entity):
        return self.get_layout_by_key(entity.dxf.owner)

    def get_layout_by_key(self, layout_key):
        for layout in self._layouts.values():
            if layout_key == layout.layout_key:
                return layout
        raise DXFKeyError("Layout with key '{}' does not exist.".format(layout_key))

    def new(self, name, dxfattribs=None):
        """ Create a new Layout.
        """
        if dxfattribs is None:
            dxfattribs = {}

        if name in self._layouts:
            raise DXFValueError("Layout '{}' already exists".format(name))

        def create_dxf_layout_entity():
            dxfattribs['name'] = name
            dxfattribs['owner'] = self._dxf_layout_management_table.dxf.handle
            dxfattribs.setdefault('taborder', len(self._layouts) + 1)
            dxfattribs['block_record'] = block_record_handle
            entity = self.drawing.objects.create_new_dxf_entity('LAYOUT', dxfattribs)
            return entity.dxf.handle

        block_layout = self.drawing.blocks.new_layout_block()
        block_record_handle = block_layout.block_record_handle
        block_record = block_layout.block_record
        layout_handle = create_dxf_layout_entity()
        block_record.dxf.layout = layout_handle

        # create valid layout entity
        layout = Layout(self.drawing, layout_handle)

        # add layout to management tables
        self._dxf_layout_management_table[name] = layout_handle
        self._layouts[name] = layout

        return layout

    def set_active_layout(self, name):
        if name == 'Model':  # reserved layout name
            raise DXFValueError("Can not set model space as active layout")
        new_active_layout = self.get(name)  # raises KeyError if no layout 'name' exists
        old_active_layout_key = self.drawing.get_active_layout_key()
        if old_active_layout_key == new_active_layout.layout_key:
            return  # layout 'name' is already the active layout

        blocks = self.drawing.blocks
        new_active_paper_space_name = new_active_layout.block_record_name

        blocks.rename_block(PAPER_SPACE, TMP_PAPER_SPACE_NAME)
        blocks.rename_block(new_active_paper_space_name, PAPER_SPACE)
        blocks.rename_block(TMP_PAPER_SPACE_NAME, new_active_paper_space_name)

    def delete(self, name):
        """ Delete layout *name* and all entities on it. Raises *KeyError* if layout *name* not exists.
        Raises *ValueError* for deleting model space.
        """
        if name == 'Model':
            raise DXFValueError("can not delete model space layout")

        layout = self._layouts[name]
        if layout.layout_key == self.drawing.get_active_layout_key():  # name is the active layout
            for layout_name in self.names():
                if layout_name not in (name, 'Model'):  # set any other layout as active layout
                    self.set_active_layout(layout_name)
                    break
        self._dxf_layout_management_table.remove(layout.name)
        del self._layouts[layout.name]
        layout.destroy()

    def active_layout(self):
        for layout in self:
            if layout.block_record_name.upper() == '*PAPER_SPACE':
                return layout
        raise DXFInternalEzdxfError('No active paper space found.')

    def write_entities_section(self, tagwriter):
        # DXF entities of the model space and the active paper space are stored in the ENTITIES section,
        # all DXF entities of other paper space layouts are stored in the BLOCK definition of the paper space layout
        # in the BLOCKS section.
        self.modelspace().write(tagwriter)
        self.active_layout().write(tagwriter)


class Layout(DXF12Layout):
    """ Layout representation

    Every layout consist of a LAYOUT entity in the OBJECTS section, an associated BLOCK in the BLOCKS section and a
    BLOCK_RECORD_TABLE entry.

    layout_key: handle of the BLOCK_RECORD, every layout entity has this handle as owner attribute (entity.dxf.owner)

    There are 3 different layout types:

    1. Model Space - not deletable, all entities of this layout are stored in the DXF file in the ENTITIES section, the
    associated '*Model_Space' block is empty, block name '*Model_Space' is mandatory, the layout name is 'Model' and it
    is mandatory.

    2. Active Layout - all entities of this layout are stored in the ENTITIES section, the
    associated '*Paper_Space' block is empty, block name '*Paper_Space' is mandatory and also marks the active
    layout, the layout name can be an arbitrary string.

    3. Inactive Layout - all entities of this layouts are stored in the associated BLOCK
    called '*Paper_SpaceN', where N is an arbitrary number, I don't know if the block name schema '*Paper_SpaceN' is
    mandatory, the layout name can be an arbitrary string.

    There is no different handling for active layouts and inactive layouts in ezdxf, this differentiation is just
    for AutoCAD important and it is not described in the DXF standard.

    Internal Structure:

    For EVERY layout exists a BlockLayout() object in the blocks section and an EntitySpace() object in the entities
    sections. the block layout entity section and the layout entity section are the SAME object.
    See Layouts.create() line after comment 'set block entity space as layout entity space'.

    ALL layouts entity spaces (also Model Space) are managed in a LayoutSpaces() object in the EntitySection() object.
    Which allows full access to all entities on all layouts at every time.

    """
    def __init__(self, drawing, layout_handle):
        dxffactory = drawing.dxffactory
        self.dxf_layout = dxffactory.wrap_handle(layout_handle)
        self._block_record_handle = self.dxf_layout.dxf.block_record

        entity_space = self._get_layout_entity_space(drawing, self.dxf_layout)
        super(Layout, self).__init__(entity_space, dxffactory, 0)
        self._layout_handle = layout_handle
        self._paperspace = 0 if self.name == 'Model' else 1
        self._repair_owner_tags()

    @staticmethod
    def _get_layout_entity_space(drawing, layout):
        block_record = drawing.dxffactory.wrap_handle(layout.dxf.block_record)
        block = drawing.blocks.get(block_record.dxf.name)
        return block.get_entity_space()

    def _repair_owner_tags(self):
        layout_key = self.layout_key
        paper_space = self._paperspace
        for entity in self:
            if entity.get_dxf_attrib('owner', default=None) != layout_key:
                entity.set_dxf_attrib('owner', layout_key)
            if entity.get_dxf_attrib('paperspace', default=0) != paper_space:
                entity.set_dxf_attrib('paperspace', paper_space)

    # start of public interface

    def __contains__(self, entity):
        if not hasattr(entity, 'dxf'):  # entity is a handle and not a wrapper class
            entity = self.get_entity_by_handle(entity)
        return True if entity.dxf.owner == self.layout_key else False

    @property
    def dxf(self):
        return self.dxf_layout.dxf

    def paper_setup(self, size=(297, 210), margins=(10, 15, 10, 15), units='mm', rotation=0, scale=16,
                    name='ezdxf', device='DWG to PDF.pc3'):
        """
        Setup plot settings and paper size and reset viewports.

        Args:
            size:
            margins: (top, right, bottom, left) hint: clockwise
            units: 'mm' or 'inch'
            rotation: 0=no rotation, 1=90deg count-clockwise, 2=upside-down, 3=90deg clockwise
            scale: int 0-32 = standard scale type or tuple(numerator, denominator) e.g. (1, 50) for 1:50
            name: paper name prefix '{name}_({width}_x_{height}_{unit})'
            device: device .pc3 configuration file or system printer name

        """
        def use_standard_scale(state):
            flags = self.dxf_layout.dxf.plot_layout_flags
            if state:
                flags = flags | USE_STANDARD_SCALE
            else:
                flags = flags & ~USE_STANDARD_SCALE
            self.dxf_layout.dxf.plot_layout_flags = flags

        if self.name == 'Model':
            raise DXFTypeError("No paper setup for model space.")
        if int(rotation) not in (0, 1, 2, 3):
            raise DXFValueError("valid rotation values: 0-3")

        if isinstance(scale, tuple):
            standard_scale = 16
            use_standard_scale(False)
        elif isinstance(scale, int):
            use_standard_scale(True)
            standard_scale = scale
            scale = Layout._scale_tuple(standard_scale)
        else:
            raise DXFTypeError("scale has to be an int or a tuple(numerator, denominator)")

        paper_width, paper_height = size
        margin_top, margin_right, margin_bottom, margin_left = margins
        units = units.lower()
        if units.startswith('inch'):
            units = 'Inches'
            plot_paper_units = 0
            unit_factor = 25.4  # inch to mm
        elif units == 'mm':
            units = 'MM'
            plot_paper_units = 1
            unit_factor = 1.0
        else:
            raise DXFValueError('Units have to be "mm" or "inch", not supported: "pixel".')

        # Setup PLOTSETTINGS
        dxf = self.dxf_layout.dxf
        dxf.page_setup_name = ''
        dxf.plot_configuration_file = device
        dxf.paper_size = '{0}_({1:.2f}_x_{2:.2f}_{3})'.format(name, paper_width, paper_height, units)
        dxf.left_margin = margin_left * unit_factor
        dxf.bottom_margin = margin_bottom * unit_factor

        dxf.right_margin = margin_right * unit_factor
        dxf.top_margin = margin_top * unit_factor
        dxf.paper_width = paper_width * unit_factor
        dxf.paper_height = paper_height * unit_factor
        dxf.scale_numerator = scale[0]
        dxf.scale_denominator = scale[1]
        dxf.plot_paper_units = plot_paper_units
        dxf.plot_rotation = rotation
        dxf.plot_origin_x_offset = 0
        dxf.plot_origin_y_offset = 0
        dxf.standard_scale_type = standard_scale

        # Setup Layout
        dxf.limmin = (0, 0)  # paper space units
        dxf.limmax = (paper_width, paper_height)
        dxf.extmin = (+1e20, +1e20, +1e20)  # AutoCAD default
        dxf.extmax = (-1e20, -1e20, -1e20)  # AutoCAD default
        self.reset_viewports()

    def reset_viewports(self):
        # remove existing viewports
        def paper_units(value):
            return value / unit_factor * scale_factor

        for viewport in self.viewports():
            self.delete_entity(viewport)

        dxf = self.dxf_layout.dxf
        if dxf.plot_paper_units == 0:  # inches
            unit_factor = 25.4
        else:  # mm
            unit_factor = 1.0

        # all paper parameters in mm!
        # all viewport parameters in paper space units inch/mm + scale factor!
        try:
            scale_factor = dxf.scale_denominator / dxf.scale_numerator
        except ZeroDivisionError:
            scale_factor = 1.

        vp_width = paper_units(dxf.paper_width) * 1.2  # paper width + 20%
        vp_height = paper_units(dxf.paper_height) * 1.2  # paper height + 20%
        # add 'main' viewport
        main_viewport = self.add_viewport(
            center=(vp_width/2, vp_height/2),  # no influence to 'main' viewport?
            size=(vp_width, vp_height),  # I don't get it, just use paper size!
            view_center_point=(vp_width/2, vp_height/2),  # same as center
            view_height=vp_height,   # view height in paper space units
        )
        main_viewport.dxf.id = 1  # set as main viewport
        dxf.viewport = main_viewport.dxf.handle

    # end of public interface

    @staticmethod
    def _std_scale(scale):
        scale = float(scale[0]), float(scale[1])
        return SCALE_TO_INDEX.get(scale, 16)

    @staticmethod
    def _scale_tuple(scale_index):
        return STD_SCALES.get(scale_index, (1, 1))

    @property
    def layout_key(self):
        return self._block_record_handle

    @property
    def block_record(self):
        return self.drawing.dxffactory.wrap_handle(self._block_record_handle)

    @property
    def block_record_name(self):
        return self.block_record.dxf.name

    @property
    def block(self):
        return self.drawing.blocks.get(self.block_record_name)

    @property
    def name(self):
        return self.dxf_layout.dxf.name

    @property
    def taborder(self):
        return self.dxf_layout.dxf.taborder

    def is_active(self):
        return self.block_record_name.upper() in ('*PAPER_SPACE', '*MODEL_SPACE')

    def _set_paperspace(self, entity):
        entity.dxf.paperspace = self._paperspace
        entity.dxf.owner = self.layout_key

    def destroy(self):
        self.delete_all_entities()
        self.drawing.blocks.delete_block(self.block.name)
        self.drawing.objects.remove_handle(self._layout_handle)
        self.drawing.entitydb.delete_handle(self._layout_handle)


class BlockLayout(DXF12BlockLayout):
    def add_entity(self, entity):
        """ Add entity to the block entity space.
        """
        # entity can be ExtendedTags() or a GraphicEntity() or inherited wrapper class
        if isinstance(entity, ExtendedTags):
            entity = self._dxffactory.wrap_entity(entity)
        entity.dxf.owner = self.block_record_handle
        self._entity_space.append(entity.dxf.handle)

    @property
    def block_record_handle(self):
        return self.block.dxf.owner

    def set_block_record_handle(self, block_record_handle):
        self.block.dxf.owner = block_record_handle
        self.endblk.dxf.owner = block_record_handle

    @property
    def block_record(self):
        return self.drawing.dxffactory.wrap_handle(self.block_record_handle)

    def get_entity_space(self):
        return self._entity_space

    def set_entity_space(self, entity_space):
        self._entity_space = entity_space

    def destroy(self):
        self.drawing.sections.tables.block_records.remove_handle(self.block_record_handle)
        super(BlockLayout, self).destroy()

    def write(self, tagwriter):
        # BLOCK section: do not write content of model space and active layout
        if self.name.upper() in ('*MODEL_SPACE', '*PAPER_SPACE'):
            save = self._entity_space
            self._entity_space = EntitySpace(self.entitydb)
            super(BlockLayout, self).write(tagwriter)
            self._entity_space = save
        else:
            super(BlockLayout, self).write(tagwriter)
