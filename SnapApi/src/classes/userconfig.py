from pydantic import BaseModel
from typing import Optional

class UserConfigDetails(BaseModel):
    name: str   
    role: str
    username:str
    password: str

class UserConfig(BaseModel):
    userdetails: UserConfigDetails
    name: str

    def __init__(self, userdetails: UserConfigDetails, name: str):
        super().__init__(userdetails=userdetails, name=name)
    
    def to_dict(self):
        return {
            "userdetails": self.userdetails.model_dump(),
            "name": self.name
        }

class LoginUserConfigRequest(BaseModel):
    username: str
    password: str
    auth_method: Optional[str] = "local"  # "ad" or "local"

class VerifyUserConfigRequest(BaseModel):
    token: str

