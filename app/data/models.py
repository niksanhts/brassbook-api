from pydantic import BaseModel, Field

class User(BaseModel):
    username: str
    full_name: str = Field(default=None)
    email: str = Field(default=None)