from enum import IntEnum
from pydantic import BaseModel, validator, constr


class ChannelType(IntEnum):
    public = 0
    private = 1


class ChannelOpenRequest(BaseModel):
    remoteid: constr(min_length=66, max_length=66, regex='[0-9a-f]*')
    private: ChannelType = ChannelType.private
    k1: constr(min_length=1)

    @validator('remoteid')
    def clean_remoteid(cls, v):
        return bytes.fromhex(v)

    @validator('private')
    def clean_private(cls, v):
        return int(v)
