#  Copyright (c) 2021, Manfred Moitzi
#  License: MIT License
from typing import TYPE_CHECKING, Iterable, Dict, Optional
import warnings

import ezdxf
from ezdxf import disassemble
from ezdxf.math import BoundingBox

if TYPE_CHECKING:
    from ezdxf.eztypes import DXFEntity

MAX_FLATTENING_DISTANCE = disassemble.Primitive.max_flattening_distance


class Cache:
    """Caching object for :class:`ezdxf.math.BoundingBox` objects.

    Args:
        uuid: use UUIDs for virtual entities

    """

    def __init__(self, uuid=False):
        self._boxes: Dict[str, BoundingBox] = dict()
        self._use_uuid = bool(uuid)
        self.hits: int = 0
        self.misses: int = 0

    def __str__(self):
        return (
            f"Cache(n={len(self._boxes)}, "
            f"hits={self.hits}, "
            f"misses={self.misses})"
        )

    def get(self, entity: "DXFEntity") -> Optional[BoundingBox]:
        assert entity is not None
        key = self._get_key(entity)
        if key is None:
            self.misses += 1
            return None
        box = self._boxes.get(key)
        if box is None:
            self.misses += 1
        else:
            self.hits += 1
        return box

    def store(self, entity: "DXFEntity", box: BoundingBox) -> None:
        assert entity is not None
        key = self._get_key(entity)
        if key is None:
            return
        self._boxes[key] = box

    def invalidate(self, entities: Iterable["DXFEntity"]) -> None:
        """Invalidate cache entries for the given DXF `entities`.

        If entities are changed by the user, it is possible to invalidate
        individual entities. Use with care - discarding the whole cache is
        the safer workflow.

        Ignores entities which are not stored in cache.

        """
        for entity in entities:
            try:
                del self._boxes[self._get_key(entity)]  # type: ignore
            except KeyError:
                pass

    def _get_key(self, entity: "DXFEntity") -> Optional[str]:
        if entity.dxftype() == "HATCH":
            # Special treatment for multiple primitives for the same
            # HATCH entity - all have the same handle:
            # Do not store boundary path they are not distinguishable,
            # which boundary path should be returned for the handle?
            return None

        key = entity.dxf.handle
        if key is None or key == "0":
            return str(entity.uuid) if self._use_uuid else None
        else:
            return key


def _resolve_fast_arg(fast: bool, kwargs) -> bool:
    if "flatten" in kwargs:
        warnings.warn(
            "Argument 'flatten' replaced by argument 'fast', "
            "'flatten' will be removed in v1.0!",
            DeprecationWarning,
        )
        fast = not bool(kwargs["flatten"])
    return fast


def multi_recursive(
    entities: Iterable["DXFEntity"],
    *,
    fast=False,
    cache: Cache = None,
    **kwargs,
) -> Iterable[BoundingBox]:
    """Yields all bounding boxes for the given `entities` **or** all bounding
    boxes for their sub entities. If an entity (INSERT) has sub entities, only
    the bounding boxes of these sub entities will be yielded, **not** the
    bounding box of the entity (INSERT) itself.

    If argument `fast` is ``True`` the calculation of Bézier curves is based on
    their control points, this may return a slightly larger bounding box.

    .. versionchanged:: 0.18

        replaced argument `flatten` by argument `fast`

    """
    fast = _resolve_fast_arg(fast, kwargs)
    flat_entities = disassemble.recursive_decompose(entities)
    primitives = disassemble.to_primitives(flat_entities)
    for primitive in primitives:
        if primitive.is_empty:
            continue

        entity = primitive.entity
        if cache is not None:
            box = cache.get(entity)
            if box is None:
                box = primitive.bbox(fast=fast)
                if box.has_data:
                    cache.store(entity, box)
        else:
            box = primitive.bbox(fast=fast)

        if box.has_data:
            yield box


def extents(
    entities: Iterable["DXFEntity"],
    *,
    fast=False,
    cache: Cache = None,
    **kwargs,
) -> BoundingBox:
    """Returns a single bounding box for all given `entities`.

    If argument `fast` is ``True`` the calculation of Bézier curves is based on
    their control points, this may return a slightly larger bounding box.
    The `fast` mode also uses a simpler and mostly inaccurate text size
    calculation instead of the more precise but very slow calculation by
    `matplotlib`.

    .. hint::

        The fast mode is not much faster for non-text based entities, so using
        the slower default mode is not a big disadvantage if a more precise text
        size calculation is important.

    .. versionchanged:: 0.18

        added fast mode, replaced argument `flatten` by argument `fast`

    """
    fast = _resolve_fast_arg(fast, kwargs)
    use_matplotlib = ezdxf.options.use_matplotlib  # save current state
    if fast:
        ezdxf.options.use_matplotlib = False
    _extends = BoundingBox()
    for box in multi_flat(entities, fast=fast, cache=cache):
        _extends.extend(box)
    ezdxf.options.use_matplotlib = use_matplotlib  # restore state
    return _extends


def multi_flat(
    entities: Iterable["DXFEntity"],
    *,
    fast=False,
    cache: Cache = None,
    **kwargs,
) -> Iterable[BoundingBox]:
    """Yields a bounding box for each of the given `entities`.

    If argument `fast` is ``True`` the calculation of Bézier curves is based on
    their control points, this may return a slightly larger bounding box.

    .. versionchanged:: 0.18

        replaced argument `flatten` by argument `fast`

    """

    def extends_(entities_: Iterable["DXFEntity"]) -> BoundingBox:
        _extends = BoundingBox()
        for _box in multi_recursive(
            entities_, fast=_resolve_fast_arg(fast, kwargs), cache=cache
        ):
            _extends.extend(_box)
        return _extends

    for entity in entities:
        box = None
        if cache:
            box = cache.get(entity)

        if box is None:
            box = extends_([entity])
            if cache:
                cache.store(entity, box)

        if box.has_data:
            yield box
