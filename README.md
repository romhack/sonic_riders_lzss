# sonic_riders_lzss
LZSS compression tool for "Sonic Riders" games


Synopsis:
```
sonic_riders_lzss.py COMMAND [OPTIONS] FILE_NAME
```
  
Description:
```
sonic_riders_lzss.py unpack [OPTIONS] IN_NAME

  Decompress given IN_NAME packed file. Output file name can be provided,
  otherwise default 'decompressed.bin' will be used.

Options:
  -o, --out_name TEXT  Output plain file name.

sonic_riders_lzss.py pack [OPTIONS] IN_NAME

  Compress plain IN_NAME file. Output file name can be provided, otherwise
  default 'compressed.bin' will be used.

Options:
  -o, --out_name TEXT  Output packed file name.
```

Install:
```
pip install -r requirements.txt
```
  
A tool for compressing and decompressing data in "Sonic Riders" games for PC and Xbox  
Compression format description:  
```
0x80 bytes compressed file header:
uintle:32 0x80000001
uintle:32 unpacked file size
padding zeroes until offset 0x80

LZ:     
1 XXXXXXXX YYYYYYYY
| |        |
| |        8 bit LZ copy length
| 8 bit LZ offset-back (distance)
compression flag

LZ also works if length > (current_position - offset), effectively unpacking from currently unpacked buffer.
For LZ to be more effective, than worst case 'fresh' raw dump, you need to lz encode 2 bytes length

Raw:
0 XXXXXXXX
| |     
| |     
| 8 bit raw byte value
non-compression flag
```
