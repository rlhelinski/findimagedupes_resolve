from __future__ import print_function
import os
import sys
from subprocess import Popen, PIPE

import argparse

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

def curate_group(group, skip_sequential=False):
    existing_files = []
    for index, path in enumerate(group):
        sys.stdout.write('.'); sys.stdout.flush()
        if os.path.isfile(path):
            existing_files.append(group[index])
    sys.stdout.write('\n')
    group = existing_files
    if skip_sequential:
        group = remove_sequential(group)
    if len(group) == 1:
        print ('Singular group')
        raise Exception()
    if len(group) == 0:
        print ('Empty group')
        raise Exception()
    group = sorted(group, key=lambda path: os.path.basename(path))
    return group

def path_get_serial(path):
    filename = os.path.basename(path)
    if filename[3] == '_':
        return int(filename[4:8])
    else:
        return int(filename.split('.')[0])

def remove_sequential(group):
    group = sorted(group)
    subset = [group[0]]
    last_serial = path_get_serial(group[0])
    for index, path in enumerate(group[1:]):
        serial_number = path_get_serial(path)
        if serial_number - last_serial != 1:
            subset.append(path)
        else:
            print('Ignoring '+path)
        last_serial = serial_number

    return subset

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='reconcile output from the `findimagedupes` program')
    parser.add_argument(
        'logfile')
    args = parser.parse_args()
    with open(args.logfile, 'r') as f:
        lines = f.readlines()

    groups = []

    for line in lines:
        paths = line[0:-1].split(' /')
        paths = [paths[0]] + ['/'+path for path in paths[1:]]
        groups.append(paths)

    skip_sequential = False

    for group_i, group in enumerate(groups):
        if len(group) > 100:
            print ('Group %d has %d files, skipping' % (group_i+1, len(group)))
        jpeginfo_d = {}
        try:
            group = curate_group(group)
        except Exception:
            continue
        for path in group:
            if os.path.isfile(path):
                sys.stdout.write('.'); sys.stdout.flush()
                jpeginfo = Popen(['jpeginfo', '-c', path],
                                 stdout=PIPE).communicate()[0]
                jpeginfo_d[path] = jpeginfo.strip()
        sys.stdout.write('\n')

        while True:
            try:
                group = curate_group(group, skip_sequential)
            except Exception:
                break

            print ('%d files in group %d/%d:' % (len(group), group_i+1,
                                                 len(groups)))
            for index, path in enumerate(group):
# TODO this could be done faster by a module
                print ('%3d: %s (%s)' % (index,
                                         jpeginfo_d[path],
                                         format_size(os.path.getsize(path))))
            resp = raw_input('Action: ')
# TODO make opening images in 'eog' an option
            if resp.startswith('d'):
                try:
                    select_index = int(resp[1:])
                except ValueError as e:
                    print (str(e))
                print ('Deleting "%s"' % group[select_index])
                os.system('gvfs-trash "%s"' % group[select_index])
                del group[select_index]
            elif resp.lower().startswith('q'):
                raise KeyboardInterrupt
            elif resp.lower().startswith('n'):
                break
            elif resp.lower().startswith('v'):
                #result_path = tempfile.mktemp()
                #p = Popen(['compare']+group, shell=True)
                #pid, sts = os.waitpid(p.pid, 0)
                #p = Popen(['display', result_path], shell=True)
                #for imgpath in group:
                    #Popen(['display', imgpath], shell=True)
                Popen(['eog']+group)
            elif resp.lower().startswith('ss'):
                skip_sequential = True
            else:
                print('Commands:')
                print('v: visualize')
                print('d[index]: delete file specified by index')
                print('n: proceed to next file group')
                print('ss: skip sequential files')
                print('q: quit')
