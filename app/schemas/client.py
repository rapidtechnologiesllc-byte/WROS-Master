from pydantic import BaseModel


class ClientListItem(BaseModel):
    id: str
    company_name: str

    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    clients: list[ClientListItem]
