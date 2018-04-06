import itertools
import sys
import struct
from io import BytesIO, SEEK_CUR, SEEK_END  # noqa

PY2 = sys.version_info[0] == 2

# Kaitai Struct runtime streaming API version, defined as per PEP-0396
# standard. Used for two purposes:
#
# * .py files generated by ksc from .ksy check that they import proper
#   KS runtime library by this version number;
# * distribution utils (setup.py) use this when packaging for PyPI
#
__version__ = '0.8'


class KaitaiStruct(object):
    def __init__(self, stream):
        self._io = stream

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        self._io.close()

    @classmethod
    def from_file(cls, filename):
        f = open(filename, 'rb')
        try:
            return cls(KaitaiStream(f))
        except Exception:
            # close file descriptor, then reraise the exception
            f.close()
            raise

    @classmethod
    def from_bytes(cls, buf):
        return cls(KaitaiStream(BytesIO(buf)))

    @classmethod
    def from_io(cls, io):
        return cls(KaitaiStream(io))


class KaitaiStream(object):
    def __init__(self, io):
        self._io = io
        self.align_to_byte()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        self._io.close()

    # ========================================================================
    # Stream positioning
    # ========================================================================

    def is_eof(self):
        io = self._io
        t = io.read(1)
        if t == b'':
            return True
        else:
            io.seek(-1, SEEK_CUR)
            return False

    def seek(self, n):
        self._io.seek(n)

    def pos(self):
        return self._io.tell()

    def size(self):
        # Python has no internal File object API function to get
        # current file / StringIO size, thus we use the following
        # trick.
        io = self._io
        # Remember our current position
        cur_pos = io.tell()
        # Seek to the end of the File object
        io.seek(0, SEEK_END)
        # Remember position, which is equal to the full length
        full_size = io.tell()
        # Seek back to the current position
        io.seek(cur_pos)
        return full_size

    # ========================================================================
    # Integer numbers
    # ========================================================================

    packer_s1 = struct.Struct('b')
    packer_s2be = struct.Struct('>h')
    packer_s4be = struct.Struct('>i')
    packer_s8be = struct.Struct('>q')
    packer_s2le = struct.Struct('<h')
    packer_s4le = struct.Struct('<i')
    packer_s8le = struct.Struct('<q')

    packer_u1 = struct.Struct('B')
    packer_u2be = struct.Struct('>H')
    packer_u4be = struct.Struct('>I')
    packer_u8be = struct.Struct('>Q')
    packer_u2le = struct.Struct('<H')
    packer_u4le = struct.Struct('<I')
    packer_u8le = struct.Struct('<Q')

    # ------------------------------------------------------------------------
    # Signed
    # ------------------------------------------------------------------------

    def read_s1(self):
        return KaitaiStream.packer_s1.unpack(self.read_bytes(1))[0]

    # ........................................................................
    # Big-endian
    # ........................................................................

    def read_s2be(self):
        return KaitaiStream.packer_s2be.unpack(self.read_bytes(2))[0]

    def read_s4be(self):
        return KaitaiStream.packer_s4be.unpack(self.read_bytes(4))[0]

    def read_s8be(self):
        return KaitaiStream.packer_s8be.unpack(self.read_bytes(8))[0]

    # ........................................................................
    # Little-endian
    # ........................................................................

    def read_s2le(self):
        return KaitaiStream.packer_s2le.unpack(self.read_bytes(2))[0]

    def read_s4le(self):
        return KaitaiStream.packer_s4le.unpack(self.read_bytes(4))[0]

    def read_s8le(self):
        return KaitaiStream.packer_s8le.unpack(self.read_bytes(8))[0]

    # ------------------------------------------------------------------------
    # Unsigned
    # ------------------------------------------------------------------------

    def read_u1(self):
        return KaitaiStream.packer_u1.unpack(self.read_bytes(1))[0]

    # ........................................................................
    # Big-endian
    # ........................................................................

    def read_u2be(self):
        return KaitaiStream.packer_u2be.unpack(self.read_bytes(2))[0]

    def read_u4be(self):
        return KaitaiStream.packer_u4be.unpack(self.read_bytes(4))[0]

    def read_u8be(self):
        return KaitaiStream.packer_u8be.unpack(self.read_bytes(8))[0]

    # ........................................................................
    # Little-endian
    # ........................................................................

    def read_u2le(self):
        return KaitaiStream.packer_u2le.unpack(self.read_bytes(2))[0]

    def read_u4le(self):
        return KaitaiStream.packer_u4le.unpack(self.read_bytes(4))[0]

    def read_u8le(self):
        return KaitaiStream.packer_u8le.unpack(self.read_bytes(8))[0]

    # ========================================================================
    # Floating point numbers
    # ========================================================================

    packer_f4be = struct.Struct('>f')
    packer_f8be = struct.Struct('>d')
    packer_f4le = struct.Struct('<f')
    packer_f8le = struct.Struct('<d')

    # ........................................................................
    # Big-endian
    # ........................................................................

    def read_f4be(self):
        return KaitaiStream.packer_f4be.unpack(self.read_bytes(4))[0]

    def read_f8be(self):
        return KaitaiStream.packer_f8be.unpack(self.read_bytes(8))[0]

    # ........................................................................
    # Little-endian
    # ........................................................................

    def read_f4le(self):
        return KaitaiStream.packer_f4le.unpack(self.read_bytes(4))[0]

    def read_f8le(self):
        return KaitaiStream.packer_f8le.unpack(self.read_bytes(8))[0]

    # ========================================================================
    # Unaligned bit values
    # ========================================================================

    def align_to_byte(self):
        self.bits = 0
        self.bits_left = 0

    def read_bits_int(self, n):
        bits_needed = n - self.bits_left
        if bits_needed > 0:
            # 1 bit  => 1 byte
            # 8 bits => 1 byte
            # 9 bits => 2 bytes
            bytes_needed = ((bits_needed - 1) // 8) + 1
            buf = self.read_bytes(bytes_needed)
            for byte in buf:
                # Python 2 will get "byte" as one-character str, thus
                # we need to convert it to integer manually; Python 3
                # is fine as is.
                if isinstance(byte, str):
                    byte = ord(byte)
                self.bits <<= 8
                self.bits |= byte
                self.bits_left += 8

        # raw mask with required number of 1s, starting from lowest bit
        mask = (1 << n) - 1
        # shift mask to align with highest bits available in self.bits
        shift_bits = self.bits_left - n
        mask <<= shift_bits
        # derive reading result
        res = (self.bits & mask) >> shift_bits
        # clear top bits that we've just read => AND with 1s
        self.bits_left -= n
        mask = (1 << self.bits_left) - 1
        self.bits &= mask

        return res

    # ========================================================================
    # Byte arrays
    # ========================================================================

    def read_bytes(self, n):
        if n < 0:
            raise ValueError(
                "requested invalid %d amount of bytes" %
                (n,)
            )
        r = self._io.read(n)
        if len(r) < n:
            raise EOFError(
                "requested %d bytes, but got only %d bytes" %
                (n, len(r))
            )
        return r

    def read_bytes_full(self):
        return self._io.read()

    def read_bytes_term(self, term, include_term, consume_term, eos_error):
        r = b''
        while True:
            c = self._io.read(1)
            if c == b'':
                if eos_error:
                    raise Exception(
                        "end of stream reached, but no terminator %d found" %
                        (term,)
                    )
                else:
                    return r
            elif ord(c) == term:
                if include_term:
                    r += c
                if not consume_term:
                    self._io.seek(-1, SEEK_CUR)
                return r
            else:
                r += c

    def ensure_fixed_contents(self, expected):
        actual = self._io.read(len(expected))
        if actual != expected:
            raise Exception(
                "unexpected fixed contents: got %r, was waiting for %r" %
                (actual, expected)
            )
        return actual

    @staticmethod
    def bytes_strip_right(data, pad_byte):
        new_len = len(data)
        if PY2:
            # data[...] must yield an integer, to compare with integer pad_byte
            data = bytearray(data)

        while new_len > 0 and data[new_len - 1] == pad_byte:
            new_len -= 1

        return data[:new_len]

    @staticmethod
    def bytes_terminate(data, term, include_term):
        new_len = 0
        max_len = len(data)
        if PY2:
            # data[...] must yield an integer, to compare with integer term
            data = bytearray(data)

        while new_len < max_len and data[new_len] != term:
            new_len += 1

        if include_term and new_len < max_len:
            new_len += 1

        return data[:new_len]

    # ========================================================================
    # Byte array processing
    # ========================================================================

    @staticmethod
    def process_xor_one(data, key):
        if PY2:
            return bytes(bytearray(v ^ key for v in bytearray(data)))
        else:
            return bytes(v ^ key for v in data)

    @staticmethod
    def process_xor_many(data, key):
        if PY2:
            return bytes(bytearray(a ^ b for a, b in zip(bytearray(data), itertools.cycle(bytearray(key)))))
        else:
            return bytes(a ^ b for a, b in zip(data, itertools.cycle(key)))

    @staticmethod
    def process_rotate_left(data, amount, group_size):
        if group_size != 1:
            raise Exception(
                "unable to rotate group of %d bytes yet" %
                (group_size,)
            )

        mask = group_size * 8 - 1
        anti_amount = -amount & mask

        r = bytearray(data)
        for i in range(len(r)):
            r[i] = (r[i] << amount) & 0xff | (r[i] >> anti_amount)
        return bytes(r)
