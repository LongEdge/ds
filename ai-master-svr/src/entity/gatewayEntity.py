from dataclasses import dataclass

@dataclass
class CGatewayEntity:
    node_no: int
    status: str
    deal_type_no: int
    version: str
    node_loc: str