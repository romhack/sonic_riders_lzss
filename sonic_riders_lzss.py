#! /usr/bin/python3
# -*- coding: utf-8 -*-
'''
sonic_riders_lzss

A tool for compressing and decompressing data in "Sonic Riders" game
for PC, Xbox and GameCube versions

Version:   0.9
Author:    Griever
Web site:  https://github.com/romhack/sonic_riders_lzss
License:   MIT License https://opensource.org/licenses/mit-license.php
'''
from typing import NamedTuple
from bitstring import ConstBitStream, Bits, pack
import click

# compression commands: raw or lz:


class RawEntry(NamedTuple):
    value: int  # just raw byte


class LzEntry(NamedTuple):
    distance: int  # offset back in unpacked buffer, 8 bits
    length: int  # copy count, 8 bits


COMPRESSED_FILE_SIGNATURE = 0x80000001
# HEADER_SIZE = 0x80  # compress header is 0x80 bytes
MAX_OFFSET = 0xFF  # lz offset is encoded with 8 bits
MAX_LEN = 0xFF  # lz length is encoded with 8 bits


def deserialize(stream, gamecube_flag):
    '''
    Deserialize given bits stream to list of compress commands entries
    Parameters
    ----------
    stream : ConstBitStream
        input bits stream, read from compressed file
    gamecube_flag: Bool
        flags that user unpacks gamecube version file

    Returns
    -------
    entries : list of RawEntries or LzEntries
    '''
    file_flag = stream.read(
        'uintbe:32') if gamecube_flag else stream.read('uintle:32')
    assert file_flag == COMPRESSED_FILE_SIGNATURE, "File compressed flag not found, aborted!"
    plain_size = stream.read(
        'uintbe:32') if gamecube_flag else stream.read('uintle:32')
    assert plain_size > 0, "Plain size is found zero, aborted!"
    stream.bytepos = 0x20 if gamecube_flag else 0x80
    entries = []
    plain_pos = 0

    while plain_pos < plain_size:
        compressed = stream.read('bool')
        if not compressed:
            entries.append(RawEntry(value=stream.read('uint:8')))
            plain_pos += 1
        else:
            dist = stream.read('uint:8')
            count = stream.read('uint:8')
            entries.append(LzEntry(dist, count))
            plain_pos += count
    return entries


def decode(entries):
    '''
    Decode given list of compression commands to plain bytes
    Parameters
    ----------
    entries : list of RawEntries or LzEntries

    Returns
    -------
    buffer : list of ints
        plain buffer of decompressed bytes

    '''
    buffer = []
    for ent in entries:
        if isinstance(ent, RawEntry):
            buffer.append(ent.value)
        else:  # lz compression
            # cycle buffer to decompress out from buffer bounds
            cyclic_buffer = buffer[-ent.distance:] * ent.length
            buffer += cyclic_buffer[:ent.length]
    return buffer


def find_lz(lst, pos):
    '''
    find best lz match for given position and haystack list

    Parameters
    ----------
    lst : list of ints
        full plain file
    pos : int
        position in plain file to search an lz match

    Returns
    -------
    LzEntry or None
        found best lz entry for this position, if not found, return None

    '''
    def common_start_len(lst, hay_start, pos):
        count = 0
        while count < MAX_LEN and pos < len(lst) and lst[hay_start] == lst[pos]:
            hay_start += 1
            pos += 1
            count += 1
        return count

    assert lst and pos < len(
        lst), "find_lz: position out of bounds or empty list!"
    candidates = []
    # max offset back is 0xFF, haystack start from pos-0xFF, trimmed by 0
    for hay_start in range(max(0, pos-MAX_OFFSET), pos):
        common_len = common_start_len(lst, hay_start, pos)
        if common_len >= 2:  # minimal efficient entry is 2 bytes long lz
            candidates.append(
                LzEntry(distance=pos-hay_start, length=common_len))
    # compare candidates first by length, next by earliest occurence
    best = max(candidates, key=lambda ent: (ent.length, ent.distance),
               default=None)

    return best


def encode(lst):
    '''
    encode given plain file to list of compression commands

    Parameters
    ----------
    lst : list of ints
        plain file to encode

    Returns
    -------
    encoded: list of RawEntries or LzEntries

    '''
    pos = 0
    encoded = []
    with click.progressbar(length=len(lst),
                           label='Encoding (1/2)') as bar:
        while pos < len(lst):
            entry = find_lz(lst, pos)
            if entry is None:  # no lz matches found, emit raw
                encoded.append(RawEntry(lst[pos]))
                pos += 1
                bar.update(1)

            else:  # lz match found, check if lazy parsing is more efficient:
                skip_entry = find_lz(lst, pos + 1)
                if isinstance(skip_entry, LzEntry) and skip_entry.length > entry.length:
                    # dump raw + skip entry match
                    encoded.append(RawEntry(lst[pos]))
                    encoded.append(skip_entry)
                    pos += skip_entry.length + 1
                    bar.update(skip_entry.length + 1)
                else:  # current lz match is most efficient, emit it
                    encoded.append(entry)
                    pos += entry.length
                    bar.update(entry.length)

    return encoded


def serialize(commands):
    '''
    serialize given compression commands to bitstream

    Parameters
    ----------
    commands : list of RawEntries or LzEntries

    Returns
    -------
    stream : Bits
        compressed bitstream

    '''
    stream = Bits()
    with click.progressbar(commands,
                           label='Serializing (2/2)',
                           length=len(commands)) as bar:
        for command in bar:
            if isinstance(command, RawEntry):  # serialize raw
                stream += pack('bool, uint:8', False, command.value)
            else:  # serialize lz
                stream += pack('bool, uint:8, uint:8', True,
                               command.distance, command.length)
    return stream


@click.group()
def cli():
    """A tool for compressing and decompressing data for Sonic Rider game.
    """
    pass


@cli.command(name='unpack', short_help='decompress file')
@click.argument('in_name')
@click.option('--out_name', '-o', default='decompressed.bin', help='Output plain file name.')
@click.option('--gamecube', is_flag=True, help='Flag for GameCube input file format.')
def decompress_file(in_name, out_name, gamecube):
    """Decompress given IN_NAME packed file.
    Output file name can be provided, otherwise default 'decompressed.bin' will be used.

    """
    packed_stream = ConstBitStream(filename=in_name)
    entries = deserialize(packed_stream, gamecube)
    buf = decode(entries)
    with open(out_name, "wb") as decoded_file:
        decoded_file.write(bytes(buf))


@cli.command(name='pack', short_help='compress file')
@click.argument('in_name')
@click.option('--out_name', '-o', default='compressed.bin', help='Output packed file name.')
@click.option('--gamecube', is_flag=True, help='Flag for GameCube output file format.')
def compress_file(in_name, out_name, gamecube):
    """Compress plain IN_NAME file.
    Output file name can be provided, otherwise default 'compressed.bin' will be used.

    """
    with open(in_name, "rb") as plain_file:
        plain = list(plain_file.read())
    encoded = encode(plain)
    serialized = serialize(encoded)
    # write compression signature, size and zeroes up to 0x80 offset
    if gamecube:
        header = pack('uintbe:32, uintbe:32', COMPRESSED_FILE_SIGNATURE,
                      len(plain)) + Bits([0]*8*(0x20-8))
    else:
        header = pack('uintle:32, uintle:32', COMPRESSED_FILE_SIGNATURE,
                      len(plain)) + Bits([0]*8*(0x80-8))
    full_stream = header + serialized
    with open(out_name, 'wb') as encoded_file:
        full_stream.tofile(encoded_file)


if __name__ == '__main__':
    cli()
