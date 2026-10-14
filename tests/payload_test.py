import sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from tools.payload import message,varint,restore_native_video,fields

def run():
    opaque=varint(100<<3)+varint(42)
    def entry(enabled):return message(1,b'carrier_vt_available_bool')+varint(5<<3)+varint(enabled)+opaque
    def carrier(enabled):return message(1,b'46011')+message(3,b'unchanged APNs')+message(4,message(2,entry(enabled))+opaque)+opaque
    unrelated=message(2,message(1,b'international')+opaque)
    before=opaque+message(2,carrier(0))+unrelated
    after=opaque+message(2,carrier(1))+unrelated
    assert restore_native_video(before)==after,'Only CT native-video boolean may change'
    assert restore_native_video(after)==after,'Correction must be idempotent'
    for bad in (unrelated,before+message(2,carrier(0)),before[:-1]):
        try:restore_native_video(bad)
        except ValueError:pass
        else:raise AssertionError('Missing, ambiguous or truncated input accepted')
    print('Payload wire preservation and rejection checks passed')

if __name__=='__main__':run()
