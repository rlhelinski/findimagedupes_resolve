from __future__ import print_function
import os
import sys
from subprocess import Popen, PIPE

def format_size(size):
    prefix = {
        0: '',
        3: 'k',
        6: 'M',
        9: 'G',
        12: 'T'
    }
    exp = 0
    size = float(size)
    while (size > 1024):
        exp += 3
        size /= 1024
    if exp == 0:
        return '%d B' % size
    return '%.3f %sB' % (size, prefix[exp])

def curate_group(group):
    existing_files = []
    for index, path in enumerate(group):
        if os.path.isfile(path):
            existing_files.append(group[index])
    group = existing_files
    if len(group) < 2:
        print ('Singular or empty group')
        raise Exception()
    group = sorted(group, key=lambda path: os.path.basename(path))
    return group

with open("findimagedupes-mac.log", 'r') as f:
    lines = f.readlines()

groups = []

for line in lines:
    paths = line[0:-1].split(' /')
    paths = [paths[0]] + ['/'+path for path in paths[1:]]
    groups.append(paths)

for group_i, group in enumerate(groups):
    jpeginfo_d = {}
    try:
        group = curate_group(group)
    except Exception:
        continue
    for path in group:
        if os.path.isfile(path):
            sys.stdout.write('.')
            sys.stdout.flush()
            jpeginfo = Popen(['jpeginfo', '-c', path], stdout=PIPE).communicate()[0]
            jpeginfo_d[path] = jpeginfo.strip()

    while True:
        try:
            group = curate_group(group)
        except Exception:
            break

        print ('%d files in group %d/%d:' % (len(group), group_i, len(groups)))
        for index, path in enumerate(group):
# TODO this could be done by a module
            print ('%3d: %s (%s)' % (index,
                                     jpeginfo_d[path],
                                     format_size(os.path.getsize(path))))
        resp = raw_input('Action: ')
        if resp.startswith('d'):
            try:
                select_index = int(resp[1:])
            except ValueError as e:
                print (str(e))
            print ('Deleting "%s"' % group[select_index])
            os.system('gvfs-trash "%s"' % group[select_index])
            del group[select_index]
        else:
            print ('Continuing')
            break
