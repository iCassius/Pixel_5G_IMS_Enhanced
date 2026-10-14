"""Lossless wire editing for the one registered legacy native-video correction."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Field:
    number: int
    wire: int
    value: object
    raw: bytes

def varint(value):
    out=bytearray()
    while value>=128:out.append((value&127)|128);value>>=7
    out.append(value);return bytes(out)

def fields(data):
    def integer(offset):
        value=0
        for shift in range(0,70,7):
            if offset>=len(data):raise ValueError('Truncated protobuf varint')
            byte=data[offset];offset+=1;value|=(byte&127)<<shift
            if byte<128:return value,offset
        raise ValueError('Oversized protobuf varint')
    offset=0
    while offset<len(data):
        start=offset;tag,offset=integer(offset);number,wire=tag>>3,tag&7
        if not number:raise ValueError('Invalid protobuf field')
        if wire==0:value,offset=integer(offset)
        elif wire in (1,5):
            size=8 if wire==1 else 4;value=data[offset:offset+size];offset+=size
            if len(value)!=size:raise ValueError('Truncated fixed protobuf field')
        elif wire==2:
            size,offset=integer(offset);value=data[offset:offset+size];offset+=size
            if len(value)!=size:raise ValueError('Truncated protobuf message')
        else:raise ValueError('Unsupported protobuf wire type')
        yield Field(number,wire,value,data[start:offset])

def message(number,data):return varint((number<<3)|2)+varint(len(data))+data

def named(data,name):
    return any(f.number==1 and f.wire==2 and f.value==name for f in fields(data))

def restore_native_video(data):
    """Only restore CT 46011 carrier_vt_available_bool; preserve all other wire bytes."""
    hits=0
    def config(data):
        nonlocal hits
        out=[]
        for entry in fields(data):
            if entry.number==2 and entry.wire==2 and named(entry.value,b'carrier_vt_available_bool'):
                values=list(fields(entry.value));booleans=[f for f in values if f.number==5 and f.wire==0]
                if len(booleans)!=1 or booleans[0].value not in (0,1):raise ValueError('Unexpected native video value')
                hits+=1
                value=b''.join(varint(5<<3)+varint(1) if f is booleans[0] else f.raw for f in values)
                out.append(message(2,value))
            else:out.append(entry.raw)
        return b''.join(out)
    out=[]
    for carrier in fields(data):
        if carrier.number==2 and carrier.wire==2 and named(carrier.value,b'46011'):
            value=b''.join(message(f.number,config(f.value)) if f.number==4 and f.wire==2 else f.raw for f in fields(carrier.value))
            out.append(message(2,value))
        else:out.append(carrier.raw)
    if hits!=1:raise ValueError('Expected exactly one registered CT native video key')
    return b''.join(out)
