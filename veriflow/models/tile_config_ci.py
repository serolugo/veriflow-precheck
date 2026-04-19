from dataclasses import dataclass


@dataclass
class TileConfigCI:
    """Simplified tile config for CI/precheck mode."""
    tile_name: str
    tile_author: str
    top_module: str
    description: str
    ports: str
    usage_guide: str
    tb_description: str
    shuttle: str

    @classmethod
    def from_dict(cls, data: dict) -> "TileConfigCI":
        return cls(
            tile_name=data.get("tile_name", "") or "",
            tile_author=data.get("tile_author", "") or "",
            top_module=data.get("top_module", "") or "",
            description=data.get("description", "") or "",
            ports=data.get("ports", "") or "",
            usage_guide=data.get("usage_guide", "") or "",
            tb_description=data.get("tb_description", "") or "",
            shuttle=data.get("shuttle", "") or "",
        )
