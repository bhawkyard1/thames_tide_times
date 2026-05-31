# /// script
# dependencies = ["pydantic"]
# ///
import json
import math
import warnings
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from pydantic import BaseModel


class PathBounds(BaseModel):
    minlat: float
    minlon: float
    maxlat: float
    maxlon: float


class LatLng(BaseModel):
    lat: float
    lon: float


class SubPath(BaseModel):
    bounds: PathBounds
    nodes: list[int]
    geometry: list[LatLng]


class RawPathData(BaseModel):
    elements: list[SubPath]


@dataclass(frozen=True)
class Node:
    id: int
    lat: float
    lon: float

    def __hash__(self):
        return hash(self.id)


minlat = 51.443362
minlon = -0.328732
maxlat = 51.527115
maxlon = 0.258179

json_path = Path(__file__).parent / "thames_path.json"

data = RawPathData.model_validate_json(json_path.read_text())

firsts: list[Node] = []
nexts: dict[Node, Node] = {}
prevs: dict[Node, Node] = {}

N = len(data.elements)
for i, path in enumerate(data.elements):
    print(f"Processing path {i}/{N}...")
    if (
            path.bounds.maxlat < minlat or
            path.bounds.minlat > maxlat or
            path.bounds.maxlon < minlon or
            path.bounds.minlon > maxlon
    ):
        continue

    nodes = [Node(nid, point.lat, point.lon) for nid, point in zip(path.nodes, path.geometry, strict=True)]
    if not nodes:
        continue

    firsts.append(nodes[0])
    for prev, next_ in pairwise(nodes):
        prevs[next_] = prev
        nexts[prev] = next_

head: Node | None = None
for node in firsts:
    if node not in prevs:
        if head is not None:
            raise ValueError(f"Found two nodes with no previous node: {head} and {node}!")
        print(f"{node} has no previous node")
        head = node
assert head is not None

ordered: list[tuple[float, float]] = []
while head:
    ordered.append((head.lat, head.lon))
    head = nexts.pop(head, None)

if nexts:
    warnings.warn(f"{len(nexts)} nodes remaining; presumably there's a break in our path!")

(Path(__file__).parent.parent / "backend" / "thames_tide_times" / "thames_path.json").write_text(
    json.dumps(ordered)
)
