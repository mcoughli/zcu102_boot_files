#!/usr/bin/python
import argparse
import os
import sys
import array
import binascii
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

BOOT_HEADER_FIELD_LIST = [
    "QSPI Width",
    "Image Identification",
    "Encryption Status",
    "FSBL Execution Address",
    "Source Offset",
    "PFW Image Length",
    "Total PFW Image Length",
    "FSBL Image Length",
    "Total FSBL Image Length",
    "Image Attributes",
    "Header Checksum",
    "Obfuscated Key",
    "Reserved",
    "FSBL/User Defined",
    "Secure Header IV",
    "Obfuscated Key IV",
    "Register Initialization"
]

BOOT_HEADER_MAP = {
    "QSPI Width":               (0x20, 0x4),
    "Image Identification":     (0x24, 0x4),
    "Encryption Status":        (0x28, 0x4),
    "FSBL Execution Address":   (0x2C, 0x4),
    "Source Offset":            (0x30, 0x4),
    "PFW Image Length":         (0x34, 0x4),
    "Total PFW Image Length":   (0x38, 0x4),
    "FSBL Image Length":        (0x3C, 0x4),
    "Total FSBL Image Length":  (0x40, 0x4),
    "Image Attributes":         (0x44, 0x4),
    "Header Checksum":          (0x48, 0x4),
    "Obfuscated Key":           (0x4C, 0x20),
    "Reserved":                 (0x6C, 0x4),
    "FSBL/User Defined":        (0x70, 0x30),
    "Secure Header IV":         (0xA0, 0xC),
    "Obfuscated Key IV":        (0xAC, 0xC),
    "Register Initialization":  (0xB8, 0x800)
}

IMAGE_HEADER_OFFSET = 0x8C0

IMAGE_HEADER_FIELD_LIST = [
    "Version",
    "Image Count",
    "First Partition Word Offset",
    "First Image Header Offset",
    "Header Authentication Word Offset",
    "Boot Device",
    "Reserved",
    "Checksum"
]

IMAGE_HEADER_MAP = {
    "Version":                              (0x00, 0x4),
    "Image Count":                          (0x04, 0x4),
    "First Partition Word Offset":          (0x08, 0x4),
    "First Image Header Offset":            (0x0C, 0x4),
    "Header Authentication Word Offset":    (0x10, 0x4),
    "Boot Device":                          (0x14, 0x4),
    "Reserved":                             (0x18, 0x20),
    "Checksum":                             (0x3C, 0x4)
}

PARTITION_HEADER_FIELD_LIST = [
    "Partition Data Word Length",
    "Extracted Data Word Length",
    "Total Partition Word Length",
    "Next Partition Word Offset",
    "Destination Execution Address LO",
    "Destination Execution Address HI",
    "Destination Load Address LO",
    "Destination Load Address HI",
    "Actual Partion Word Offset",
    "Attributes",
    "Reserved",
    "Checksum Word Offset",
    "Reserved",
    "Authentication Certificate Word Offset",
    "unused",
    "Header Checksum"
]

PARTITION_HEADER_MAP = {
    "Partition Data Word Length":               (0x00, 0x4),
    "Extracted Data Word Length":               (0x04, 0x4),
    "Total Partition Word Length":              (0x08, 0x4),
    "Next Partition Word Offset":               (0x0C, 0x4),
    "Destination Execution Address LO":         (0x10, 0x4),
    "Destination Execution Address HI":         (0x14, 0x4),
    "Destination Load Address LO":              (0x18, 0x4),
    "Destination Load Address HI":              (0x1C, 0x4),
    "Actual Partion Word Offset":               (0x20, 0x4),
    "Attributes":                               (0x24, 0x4),
    "Reserved":                                 (0x28, 0x4),
    "Checksum Word Offset":                     (0x2C, 0x4),
    "Reserved":                                 (0x30, 0x4),
    "Authentication Certificate Word Offset":   (0x34, 0x4),
    "unused":                                   (0x38, 0x4),
    "Header Checksum":                          (0x3C, 0x4)
}

SECURE_HEADER_OFFSET = 0x400
SECURE_HEADER_TAG_WIDTH = 0x10
BLOCK_0_KEY_WIDTH = 0x20
BLOCK_0_IV = 0x10

def load_file_into_array(file_path):
    file_array = array.array('B')
    file_size = os.path.getsize(args.boot_file)
    with open(args.boot_file) as boot_file_handle:
        file_array.fromfile(boot_file_handle, file_size)
    return file_array

def word_to_int(boot_file_array, offset):
    out = 0
    for i in reversed(range(4)):
        out = out << 8
        out = out + boot_file_array[offset + i]
    return out

def get_secure_header_iv(boot_file_array):
    iv = []
    iv_offset, length = BOOT_HEADER_MAP["Secure Header IV"]
    for i in reversed(range(length)):
        iv[i] = boot_file_array[iv_offset + i]
    return iv


def get_source_info(boot_file_array, pfw=False):
    source_offset = 0
    source_offset_offset, source_offset_length = BOOT_HEADER_MAP["Source Offset"]
    source_offset = word_to_int(boot_file_array, source_offset_offset)

    if pfw:
        image_field = "PFW Image Length"
    else:
        image_field = "FSBL Image Length"

    image_offset, image_length = BOOT_HEADER_MAP[image_field]
    source_length = word_to_int(boot_file_array, image_offset)

    return source_offset, source_length

#TODO: assume no pfw firmware for now
def decrypt_fsbl(boot_file_array):
    source_offset, source_length = get_source_info(boot_file_array)
    iv = get_secure_header_iv
    backend = default_backend()
    key = bytes(bytearray.fromhex(b'AD00C023E238AC9039EA984D49AA8C819456A98C124AE890ACEF002100128932'))
    iv = bytes(iv)
    tag = b'0'*16
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=backend)
    decryptor = cipher.decryptor()
    array_data = array.array('B')
    for i in range(source_length/4):
        current_word = get_word_at_address(boot_file_array, source_offset + i*4)
        # current_word = array.array('B')
        # for byte in range(4):
        #     current_word.append(boot_file_array[source_offset + i*4 + byte])
        # current_word.byteswap()
        array_data.extend(current_word)
    pt = decryptor.update(array_data.tostring()) + decryptor.finalize()
    print hex(pt)

def get_word_at_address(boot_file_array, address):
    current_word = array.array('B')
    for byte in range(4):
        current_word.append(boot_file_array[address + byte])
        # print boot_file_array[address + byte]
    # current_word.byteswap()
    current_word_2 = array.array('B')
    for i in reversed(range(4)):
        current_word_2.append(current_word[i])
    return current_word_2

def print_field_value(field, field_data):
    field_str = "{}: 0x".format(field)
    for i in range(len(field_data)):
        field_str = field_str + "{:02X}".format(field_data[i])
    print field_str

def read_field_data(boot_file_array, field_offset, field_width, base_address=0):
    field_value = array.array('B')
    current_offset = field_offset + base_address
    for i in range(field_width/4):
        field_value.extend(get_word_at_address(boot_file_array,
                                               current_offset))
        current_offset = current_offset + 4
    return field_value

def encrypt_fsbl(boot_file_array):
    source_offset, source_length = get_source_info(boot_file_array)
    iv = get_secure_header_iv
    backend = default_backend()
    key = bytes(bytearray.fromhex(b'AD00C023E238AC9039EA984D49AA8C819456A98C124AE890ACEF002100128932'))
    iv = bytes(iv)
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=backend)
    encryptor = cipher.encryptor()
    array_data = array.array('B')
    for i in range(source_length/4):
        current_word = array.array('B')
        for byte in range(4):
            current_word.append(boot_file_array[source_offset + i*4 + byte])
        current_word.byteswap()
        array_data.extend(current_word)
    pt = encryptor.update(array_data.tostring()) + encryptor.finalize()
    print type(encryptor.tag)
    print "GCM auth tag: 0x{}\n".format(binascii.hexlify(encryptor.tag))


def parse_boot_header(boot_file_array, print_registers=False):
    print "Boot Header:"
    for field in BOOT_HEADER_FIELD_LIST:
        if field == "Register Initialization" and not print_registers:
            continue
        field_offset, field_width = BOOT_HEADER_MAP[field]
        field_value = read_field_data(boot_file_array,
                                      field_offset,
                                      field_width)
        print_field_value(field, field_value)
        # field_value = array.array('B')
        # field_str = "{}: 0x".format(field)
        # num_words = field_width/4
        # for i in reversed(range(field_offset, field_offset + field_width)):
        #     field_str = field_str + "{0:X}".format(boot_file_array[i])
        # print field_str
    print ""

def parse_image_table(boot_file_array, print_reserved=False):
    #since the boot file appears to be word-aligned, the image table
    #appears to start on the next word-aligned address
    #which is at 0xBC0, as the boot header ends at 0x8B4
    print "Image Table:"
    for field in IMAGE_HEADER_FIELD_LIST:
        if field == "Reserved" and not print_reserved:
            continue
        image_field_offset, image_field_length = IMAGE_HEADER_MAP[field]
        field_value = read_field_data(boot_file_array,
                                      image_field_offset,
                                      image_field_length,
                                      base_address=IMAGE_HEADER_OFFSET)
        print_field_value(field, field_value)
    print ""

def get_first_partition_offsets(boot_file_array):
    #get partition header location
    first_partition, first_partition_width = IMAGE_HEADER_MAP["First Partition Word Offset"]
    first_partition_word_offset = word_to_int(boot_file_array,
                                              IMAGE_HEADER_OFFSET + first_partition)
    first_partition_offset = first_partition_word_offset*4
    #get image header location
    first_image, first_image_width = IMAGE_HEADER_MAP["First Image Header Offset"]
    first_image_word_offset = word_to_int(boot_file_array,
                                          IMAGE_HEADER_OFFSET + first_image)
    first_image_offset = first_image_word_offset*4

    image_count_offset, image_count_width = IMAGE_HEADER_MAP["Image Count"]
    image_count = word_to_int(boot_file_array,
                              IMAGE_HEADER_OFFSET + image_count_offset)

    return first_partition_offset, first_image_offset, image_count

def print_image_headers(boot_file_array):
    first_partition_offset, first_image_offset, image_count = get_first_partition_offsets(boot_file_array)
    last_image_header_found = False
    current_image_header = first_image_offset
    image_header_count = 0
    while not last_image_header_found:
        next_image_header = word_to_int(boot_file_array,
                                        current_image_header)*4
        if next_image_header == 0:
            last_image_header_found = True
        last_word_found = False
        current_offset = current_image_header
        print "Image Header {}".format(image_header_count)
        current_image_bytes = 0
        while not last_word_found:
            word_str = "Unknown word: 0x"
            if current_offset == current_image_header:
                word_str = "Next image header offset: 0x"
            elif current_offset == current_image_header + 4:
                word_str = "Partition offset: 0x"
            barrier_value_encountered = 0
            for i in reversed(range(current_offset, current_offset+4)):
                word_str = word_str + "{:02X}".format(boot_file_array[i])
                if boot_file_array[i] == 0xFF:
                    barrier_value_encountered = barrier_value_encountered + 1
            if barrier_value_encountered == 4:
                last_word_found = True
                break
            current_image_bytes = current_image_bytes + 4
            print word_str
            current_offset = current_offset + 4
        print "Number of bytes in image: {}\n".format(current_image_bytes)
        current_image_header = next_image_header
        image_header_count = image_header_count + 1

def print_partition_headers(boot_file_array, print_headers=True):
    first_partition_offset, first_image_offset, image_count = get_first_partition_offsets(boot_file_array)
    current_partition_base = first_partition_offset
    partition_locations = []
    for i in range(image_count):
        if current_partition_base < 0:
            if print_headers:
                print "Partition offset for partition {} not found".format(i)
            break
        if print_headers:
            print "Partition Table {}:".format(i)
        next_partition_base = -1
        for field in PARTITION_HEADER_FIELD_LIST:
            # if field == "Reserved" and not print_reserved:
            #     continue
            image_field_offset, image_field_length = PARTITION_HEADER_MAP[field]
            field_value = read_field_data(boot_file_array,
                                          image_field_offset,
                                          image_field_length,
                                          base_address=current_partition_base)
            if print_headers:
                print_field_value(field, field_value)
            if field == "Next Partition Word Offset":
                next_partition_base = word_to_int(boot_file_array,
                                                  current_partition_base + image_field_offset)*4
            if field == "Actual Partion Word Offset":
                actual_offset = word_to_int(boot_file_array,
                                            current_partition_base + image_field_offset)*4
                partition_locations.append(actual_offset)
        print ""
        current_partition_base = next_partition_base
    return partition_locations

def get_secure_header_iv(boot_file_array):
    secure_iv_offset, secure_iv_width = BOOT_HEADER_MAP["Secure Header IV"]
    # print hex(secure_iv_offset)
    # print hex(secure_iv_width)
    secure_header_iv = array.array('B')
    for tag_word in range(secure_iv_offset, secure_iv_offset + secure_iv_width, 0x4):
        # for i in reversed(range(tag_word, tag_word + 4)):
        for i in range(tag_word, tag_word + 4):
            secure_header_iv.append(boot_file_array[i])
    return secure_header_iv

def decrypt_secure_header(boot_file_array, partition_number=0):
    partition_locations = print_partition_headers(boot_file_array, print_headers=False)
    partion_data_offset = partition_locations[partition_number]
    #secure header comes before data
    secure_header_offset = partion_data_offset - SECURE_HEADER_OFFSET
    secure_header_tag = array.array('B')
    secure_header_tag_offset = partion_data_offset - SECURE_HEADER_TAG_WIDTH
    for tag_word in range(secure_header_tag_offset, secure_header_tag_offset + SECURE_HEADER_TAG_WIDTH, 0x4):
        # for i in reversed(range(tag_word, tag_word + 4)):
        for i in range(tag_word, tag_word + 4):
            secure_header_tag.append(boot_file_array[i])
    secure_header_data = array.array('B')
    for header_word in range(secure_header_offset, secure_header_tag_offset, 0x4):
        # for i in reversed(range(header_word, header_word + 4)):
        for i in range(header_word, header_word + 4):
            secure_header_data.append(boot_file_array[i])


    secure_header_iv = get_secure_header_iv(boot_file_array)
    backend = default_backend()
    key = bytearray.fromhex(b'AD00C023E238AC9039EA984D49AA8C819456A98C124AE890ACEF002100128932')
    print "Key: 0x",
    for i in range(len(key)):
        print "{:02X}".format(key[i]),
    print ""
    # iv = secure_header_iv.tostring()
    iv = bytes(bytearray(secure_header_iv))
    print "IV: 0x",
    for i in range(len(secure_header_iv)):
        print "{:02X}".format(secure_header_iv[i]),
    print ""
    # print secure_header_iv
    # print "IV: {}".format(iv)
    # tag = secure_header_tag.tostring()
    tag = bytes(bytearray(secure_header_tag))
    print "Tag: 0x",
    for i in range(len(secure_header_tag)):
        print "{:02X}".format(secure_header_tag[i]),
    print ""
    # print "Tag: {}".format(tag)
    cipher = Cipher(algorithms.AES(bytes(key)), modes.GCM(iv, tag), backend=backend)
    decryptor = cipher.decryptor()
    # array_data = array.array('B')
    # for i in range(source_length/4):
    #     current_word = get_word_at_address(boot_file_array, source_offset + i*4)
    #     # current_word = array.array('B')
    #     # for byte in range(4):
    #     #     current_word.append(boot_file_array[source_offset + i*4 + byte])
    #     # current_word.byteswap()
    #     array_data.extend(current_word)
    pt = decryptor.update(bytes(bytearray(secure_header_data))) + decryptor.finalize()
    print hex(pt)

def encrypt_from_data(boot_file_array, data_array, outfile="encrypted.out"):
    header_iv = get_secure_header_iv(boot_file_array)
    backend = default_backend()
    key = bytearray.fromhex(b'AD00C023E238AC9039EA984D49AA8C819456A98C124AE890ACEF002100128932')
    iv = bytes(bytearray(header_iv))
    print "IV: 0x",
    for i in range(len(header_iv)):
        print "{:02X}".format(header_iv[i]),
    print ""
    cipher = Cipher(algorithms.AES(bytes(key)), modes.GCM(iv), backend=backend)
    encryptor = cipher.encryptor()
    array_data = array.array('B')
    # for i in range(source_length/4):
    #     current_word = array.array('B')
    #     for byte in range(4):
    #         current_word.append(boot_file_array[source_offset + i*4 + byte])
    #     current_word.byteswap()
    #     array_data.extend(current_word)
    ct = encryptor.update(data_array.tostring()) + encryptor.finalize()
    print type(encryptor.tag)
    with open(outfile, 'w') as outfile_handle:
        outfile_handle.write(ct)
    print "GCM auth tag: 0x{}\n".format(binascii.hexlify(encryptor.tag))
    return ct, encryptor.tag


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot_file",
                        help="File to analyze, such as boot.bin",
                        required=True)
    parser.add_argument("--boot_header",
                        help="Print boot header",
                        action='store_true')
    parser.add_argument("--print_register_initialization",
                        help="Print Register Initialization when printing boot "
                        "header",
                        action='store_true')
    parser.add_argument("--encrypt_fsbl",
                        help="Attempt to encrypt the fsbl",
                        action='store_true')
    parser.add_argument("--image_table",
                        help="Print the image table",
                        action='store_true')
    parser.add_argument("--print_image_header_reserved",
                        help="Print the reserved fields in the image table "
                        "when printing the image table",
                        action='store_true')
    parser.add_argument("--print_image_headers",
                        help="Print the image headers",
                        action='store_true')
    parser.add_argument("--print_partition_headers",
                        help="Print partition headers",
                        action='store_true')
    parser.add_argument("--decrypt_secure_header",
                        type=int,
                        help="Decrypt this partiton secure header")
    parser.add_argument("--encrypt_file",
                        help="Encrypt the data in this file and show the "
                        "resulting ct and GCM tag")
    args = parser.parse_args()

    if not os.path.exists(args.boot_file):
        print "File does not exist or is inaccessible"
        sys.exit(-1)

    if not os.path.isfile(args.boot_file):
        print "Path is not a file"
        sys.exit(-1)

    file_array = load_file_into_array(args.boot_file)
    if args.boot_header:
        parse_boot_header(file_array,
                          print_registers=args.print_register_initialization)

    # print get_source_info(file_array)
    # decrypt_fsbl(file_array)

    if args.image_table:
        parse_image_table(file_array,
                          print_reserved=args.print_image_header_reserved)

    if args.print_image_headers:
        print_image_headers(file_array)

    if args.print_partition_headers:
        print_partition_headers(file_array)

    if args.decrypt_secure_header is not None:
        print "test"
        decrypt_secure_header(file_array,
                              partition_number=args.decrypt_secure_header)

    if args.encrypt_file is not None:
        file_ok = True
        if not os.path.exists(args.encrypt_file):
            print "File to encrypt does not exist or is inaccessible"
            file_ok = False

        if not os.path.isfile(args.encrypt_file):
            print "Path to file to encrypt is not a file"
            file_ok = False

        if file_ok:
            file_data_to_encrypt = load_file_into_array(args.encrypt_file)
            pt, tag = encrypt_from_data(file_array, file_data_to_encrypt)


    if args.encrypt_fsbl:
        encrypt_fsbl(file_array)
