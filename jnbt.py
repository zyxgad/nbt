
import struct
import re
import json
import base64
import gzip
from . import nbt

__all__ = ['NbtJsonEncoder', 'NbtJsonDecoder', 'nbtToJson', 'jsonToNbt']

FLOAT_STRUCT = struct.Struct('<f')
DOUBLE_STRUCT = struct.Struct('<d')

HEX_BASE = '0123456789abcdef'
def bytesToHex(bts, short=True):
  bts = bytearray(bts)
  if not short:
    return bts.hex()
  for i in range(len(bts)):
    if bts[i] != 0:
      break
  else:
  # if i == len(bts):
    return '0'
  h = bts[i:].hex()
  return h[1:] if h[0] == '0' else h

def hexToBytes(hstr, leng=0):
  if len(hstr) % 2 == 1: hstr = '0' + hstr
  barr = bytearray.fromhex(hstr)
  for _ in range(leng - len(barr)): barr.insert(0, 0x00)
  return bytes(barr)

class NbtJsonEncoder(json.JSONEncoder):
  ESCAPE = re.compile(r'[\x00-\x1f\\"\b\f\n\r\t]')
  ESCAPE_ASCII = re.compile(r'([\\"]|[^\ -~])')
  ESCAPE_DCT = {
    '\\': '\\\\',
    '"': '\\"',
    '\b': '\\b',
    '\f': '\\f',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
  }
  for i in range(0x20):
    ESCAPE_DCT.setdefault(chr(i), '\\x{0:02x}'.format(i))

  @staticmethod
  def _string_encoder(s):
    """Return an ASCII-only JSON representation of a Python string"""
    def replace(match):
      s = match.group(0)
      if s in NbtJsonEncoder.ESCAPE_DCT:
        return NbtJsonEncoder.ESCAPE_DCT[s]
      n = ord(s)
      if n < 0x10000:
        return '\\u{0:04x}'.format(n)
      # surrogate pair
      n -= 0x10000
      s1 = 0xd800 | ((n >> 10) & 0x3ff)
      s2 = 0xdc00 | (n & 0x3ff)
      return '\\u{0:04x}\\u{1:04x}'.format(s1, s2)
    return '"' + NbtJsonEncoder.ESCAPE_ASCII.sub(replace, s) + '"'

  def iterencode(self, o, _one_shot=False):
    markers = {} if self.check_circular else None

    _iterencode = _make_json_iterencode(
      markers, self.default, NbtJsonEncoder._string_encoder, self.indent,
      self.key_separator, self.item_separator, self.sort_keys,
      self.skipkeys, _one_shot)
    return _iterencode(o, 0)

def _make_json_iterencode(markers, _default, _encoder, _indent,
    _key_separator, _item_separator, _sort_keys, _skipkeys, _one_shot,
    ## HACK: hand-optimized bytecode; turn globals into locals
    ValueError=ValueError,
    id=id,
    isinstance=isinstance
  ):

  if _indent is not None and not isinstance(_indent, str):
    _indent = ' ' * _indent

  def _encode_gzip(data):
    zdata = base64.b64encode(gzip.compress(data)).decode('ascii')
    while zdata[-1] == '=': zdata = zdata[:-1]
    return '>' + zdata

  def _nbt_num(value):
    if value.__class__.id == nbt.TAG_FLOAT:
      formater = FLOAT_STRUCT
    elif value.__class__.id == nbt.TAG_DOUBLE:
      formater = DOUBLE_STRUCT
    else:
      formater = value.fmt
    return bytesToHex(formater.pack(value.value))

  def _nbt_string(value):
    if not value.value:
      return '""'
    if value.value.isascii() and value.value.isprintable() and\
      ',' not in value.value and '"' not in value.value and '\\' not in value.value and ' ' not in value.value:
      return value.value
    return _encoder(value.value)

  def _nbt_array(array):
    if array.__class__.id == nbt.TAG_BYTE_ARRAY:
      return bytesToHex(array.value, short=False)
    array.update_fmt(len(array.value))
    return bytesToHex(array.fmt.pack(*array.value), short=False)

  def _iterencode_list(lst, _current_indent_level, in_list=False, first_item=False):
    if markers is not None:
      markerid = id(lst)
      if markerid in markers:
        raise ValueError("Circular reference detected")
      markers[markerid] = lst
    if not in_list or first_item: yield HEX_BASE[int(lst.tagID)]
    # yield '['
    if len(lst.tags) == 0:
      if in_list: yield ']'
      return
    if _indent is not None and lst.tagID == nbt.TAG_COMPOUND:
      _current_indent_level += 1
      item_separator = '\n' + _indent * _current_indent_level
    else:
      item_separator = _item_separator
    yield from _iterencode(lst.tags[0], _current_indent_level, in_list=True, first_item=not in_list or first_item)
    for value in lst.tags[1:]:
      yield item_separator
      yield from _iterencode(value, _current_indent_level, in_list=True)
    yield ']'
    if markers is not None:
      del markers[markerid]

  def _iterencode_compound(dct, _current_indent_level, in_list=False):
    if markers is not None:
      markerid = id(dct)
      if markerid in markers:
        raise ValueError("Circular reference detected")
      markers[markerid] = dct
    # if in_list: yield '{'
    if len(dct.tags) == 0:
      yield '}'
      return
    if _indent is not None:
      _current_indent_level += 1
      item_separator = '\n' + _indent * _current_indent_level
    else:
      item_separator = _item_separator
    value = dct.tags[0]
    yield value.name + _key_separator
    yield from _iterencode(value, _current_indent_level)
    for value in dct.tags[1:]:
      yield item_separator + value.name + _key_separator
      yield from _iterencode(value, _current_indent_level)
      # yield '\n' + _indent * _current_indent_level
    yield '}'
    if markers is not None:
      del markers[markerid]

  def _iterencode(o, _current_indent_level, in_list=False, first_item=False):
    if not in_list: yield HEX_BASE[int(o.__class__.id)]
    if o.__class__.id == nbt.TAG_END:
      yield '0'
    elif isinstance(o, nbt._TAG_Numeric):
      yield _nbt_num(o)
    elif o.__class__.id == nbt.TAG_STRING:
      yield _nbt_string(o)
    elif o.__class__.id == nbt.TAG_BYTE_ARRAY or o.__class__.id == nbt.TAG_INT_ARRAY or o.__class__.id == nbt.TAG_LONG_ARRAY:
      s = _nbt_array(o)
      if len(s) > 256:
        zs = _encode_gzip(hexToBytes(s))
        s = zs if len(s) > len(zs) else s
      yield s
    elif o.__class__.id == nbt.TAG_LIST:
      s = ''.join(_iterencode_list(o, _current_indent_level, in_list=in_list, first_item=first_item))
      if len(s) > 256:
        zs = _encode_gzip(s.encode('ascii'))
        s = zs if len(s) > len(zs) else s
      yield s
    elif o.__class__.id == nbt.TAG_COMPOUND:
      yield from _iterencode_compound(o, _current_indent_level, in_list=in_list)
    else:
      if markers is not None:
        markerid = id(o)
        if markerid in markers:
          raise ValueError("Circular reference detected")
        markers[markerid] = o
      o = _default(o)
      yield from _iterencode(o, _current_indent_level)
      if markers is not None:
        del markers[markerid]
  return _iterencode

def nbtToJson(obj):
  return json.dumps(obj, indent=0, separators=(',', ':'), cls=NbtJsonEncoder)

########################

class NbtJsonDecoder(json.JSONDecoder):
  NUMBER_RE = re.compile(
      r'[0-9A-Fa-f]+',
      (re.VERBOSE | re.MULTILINE | re.DOTALL))
  STR_MATCH = re.compile(r'[0-9A-Za-z~!@$%()\-_+=|:.<>/?]+')
  B64_MATCH = re.compile(r'[0-9A-Za-z+/]+')
  BACKSLASH = {
    '"': '"', '\\': '\\', '/': '/',
    'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t',
  }
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.scan_once = _make_scanner(self)

def _make_scanner(context):
  memo = context.memo
  def skipwhite(string, idx, whites=' \t\f', oneline=False):
    if not oneline:
      whites += '\r\n'
    slen = len(string)
    while idx < slen and string[idx] in whites:
      idx += 1
    return idx

  def _parse_gzip(string, idx):
    data = NbtJsonDecoder.B64_MATCH.match(string, idx).group(0)
    idx += len(data)
    while len(data) % 4 != 0: data += '='
    return gzip.decompress(base64.b64decode(data)), idx

  def _parse_num(string, idx, type_):
    snumber = NbtJsonDecoder.NUMBER_RE.match(string, idx).group(0)
    idx += len(snumber)
    assert not string[idx].isidentifier()
    cls = nbt.TAGLIST[type_]
    if type_ == nbt.TAG_FLOAT:
      formater = FLOAT_STRUCT
    elif type_ == nbt.TAG_DOUBLE:
      formater = DOUBLE_STRUCT
    else:
      formater = cls.fmt
    return cls(value=formater.unpack(hexToBytes(snumber, leng=cls.fmt.size))[0]), idx

  def _parse_array(string, idx, type_):
    if string[idx] in ' \t\f\r\n,]}':
      array = nbt.TAGLIST[type_]()
      if type_ == nbt.TAG_BYTE_ARRAY:
        array.value = b''
      else:
        array.update_fmt(0)
        array.value = []
      return array, idx
    if string[idx] == '>':
      numbytes, idx = _parse_gzip(string, idx + 1)
    else:
      snumber = NbtJsonDecoder.NUMBER_RE.match(string, idx).group(0)
      idx += len(snumber)
      numbytes = hexToBytes(snumber)
    array = nbt.TAGLIST[type_]()
    if type_ == nbt.TAG_BYTE_ARRAY:
      array.value = bytearray(numbytes)
      return array, idx
    size = {nbt.TAG_INT_ARRAY: 4, nbt.TAG_LONG_ARRAY: 8}[type_]
    array.update_fmt(len(numbytes) // size)
    array.value = array.fmt.unpack(numbytes)
    return array, idx

  def _decode_xXX(string, idx):
    return chr(int(string[idx:idx + 2], 16))

  def _decode_uXXXX(string, idx):
    v = int(string[idx:idx + 4], 16)
    idx += 4
    if 0xd800 <= v < 0xdc00 and s[idx:idx + 2] == '\\u':
      v2 = int(string[idx:idx + 4], 16)
      if 0xdc00 <= v2 < 0xe000:
        v = 0x10000 + (((v - 0xd800) << 10) | (v2 - 0xdc00))
        idx += 6
    return v, idx

  def _parse_string0(string, idx):
    nbt_str = nbt.TAG_String(value='')
    while True:
      v = string[idx]
      if v == '"':
        idx += 1
        break
      if v == '\\':
        idx += 1
        esc = string[idx]
        if esc in BACKSLASH:
          v = esc
        elif esc == 'x':
          v = _decode_xXX(string, idx + 1)
          idx += 2
        elif esc == 'u':
          v, idx = _decode_uXXXX()
        else:
          raise json.JSONDecodeError("Invalid \\escape: {0!r}".format(esc), string, idx - 1)
      nbt_str.value += v
      idx += 1
    return nbt_str, idx

  def _parse_string(string, idx):
    if string[idx] == '"':
      return _parse_string0(string, idx + 1)
    nbt_str = nbt.TAG_String(value=NbtJsonDecoder.STR_MATCH.match(string, idx).group(0))
    return nbt_str, idx + len(nbt_str.value)

  def _parse_list(string, idx, in_list=False, is_first=False, type_=None):
    use_zip = string[idx] == '>'
    if use_zip:
      data, idx_ = _parse_gzip(string, idx + 1)
      string = data.decode('ascii')
      idx = 0
    nbt_list = nbt.TAG_List()
    nbt_list.tagID = type_
    if nbt_list.tagID is None:
      nbt_list.tagID = int(string[idx], 16)
      idx += 1
    idx = skipwhite(string, idx, oneline=True)
    if string[idx] in '\r\n]}':
      return nbt_list, (idx_ if use_zip else (idx + 1 if string[idx] == ']' else idx))
    first = False
    list_child = nbt_list.tagID == nbt.TAG_LIST
    if list_child and not in_list or is_first:
      first = True
      t = int(string[idx], 16)
      idx += 1
    slen = len(string)
    while idx < slen:
      value, idx = (
        _parse_list(string, idx, in_list=True, is_first=first, type_=t)
        if list_child else
        _scan_once(string, idx, nexttype=nbt_list.tagID)
      )
      if first:
        first = False
      nbt_list.tags.append(value)
      idx = skipwhite(string, idx, oneline=True)
      if idx >= len(string): break
      if string[idx] == ']':
        idx += 1
        break
      if string[idx] == '}':
        break
      if string[idx] in '\r\n,':
        idx += 1
        continue
      assert False
    return nbt_list, idx_ if use_zip else idx

  def _parse_compound(string, idx):
    if string[idx] == '{': idx += 1
    obj = nbt.TAG_Compound()
    idx = skipwhite(string, idx)
    if string[idx] == '}':
      return obj, idx + 1
    slen = len(string)
    while idx < slen:
      idx0 = string.index(':', idx)
      key = string[idx:idx0]
      value, idx = _scan_once(string, idx0 + 1)
      value.name = key
      obj.tags.append(value)
      idx = skipwhite(string, idx, oneline=True)
      if idx >= len(string): break
      if string[idx] == '}':
        idx += 1
        break
      if string[idx] in '\r\n,':
        idx += 1
        continue
      raise json.JSONDecodeError('Unexpected char ' + repr(string[idx]), string, idx)
    return obj, idx

  _DECODER_MAP = {
    nbt.TAG_END: lambda s, i: (nbt._TAG_End.INSTANCE, i),
    nbt.TAG_BYTE  : lambda s, i: _parse_num(s, i, nbt.TAG_BYTE),
    nbt.TAG_SHORT : lambda s, i: _parse_num(s, i, nbt.TAG_SHORT),
    nbt.TAG_INT   : lambda s, i: _parse_num(s, i, nbt.TAG_INT),
    nbt.TAG_LONG  : lambda s, i: _parse_num(s, i, nbt.TAG_LONG),
    nbt.TAG_FLOAT : lambda s, i: _parse_num(s, i, nbt.TAG_FLOAT),
    nbt.TAG_DOUBLE: lambda s, i: _parse_num(s, i, nbt.TAG_DOUBLE),
    nbt.TAG_BYTE_ARRAY: lambda s, i: _parse_array(s, i, nbt.TAG_BYTE_ARRAY),
    nbt.TAG_STRING: _parse_string,
    nbt.TAG_LIST: _parse_list,
    nbt.TAG_COMPOUND: _parse_compound,
    nbt.TAG_INT_ARRAY: lambda s, i: _parse_array(s, i, nbt.TAG_INT_ARRAY),
    nbt.TAG_LONG_ARRAY: lambda s, i: _parse_array(s, i, nbt.TAG_LONG_ARRAY)
  }
  def _scan_once(string, idx, nexttype=None):
    idx = skipwhite(string, idx)
    if idx >= len(string):
      raise StopIteration(idx) from None
    if nexttype is None:
      nexttype = int(string[idx], 16)
      idx += 1
    if nexttype not in _DECODER_MAP:
      raise ValueError(f'type {nexttype} not know')
    return _DECODER_MAP[nexttype](string, idx)

  def scan_once(string, idx):
    try:
      return _scan_once(string, idx)
    finally:
      memo.clear()

  return scan_once

def jsonToNbt(value):
  nbtf = nbt.NBTFile()
  nbtf.tags = json.loads(value, cls=NbtJsonDecoder).tags
  return nbtf
