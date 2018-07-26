from __future__ import print_function
import os
import sys
from subprocess import Popen, PIPE
import configparser
import PIL.Image
import PIL.ExifTags

import argparse

class CurateException(Exception):
    pass


class GetSerialError(Exception):
    pass


class ConfigManager:
    'Load and save user data'

    def __init__(self, file_path):
        self.file_path = file_path
        self.config = configparser.RawConfigParser()
        if (os.path.isfile(self.file_path)):
            self.load()
        else:
            self.load_defaults()

    def __del__(self):
        self.save()

    def load(self):
        self.config.read(self.file_path)

    def load_defaults(self):
        pass

    def save(self):
        with open(self.file_path, 'w') as configfile:
            self.config.write(configfile)


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
        if os.path.isfile(path):
            sys.stdout.write('.'); sys.stdout.flush()
            existing_files.append(group[index])
        else:
            sys.stdout.write('x')
    sys.stdout.write('\n')
    group = existing_files #.copy()
    if skip_sequential:
        try:
            group = remove_sequential(group)
        except GetSerialError:
            print('Failed to detect serial numbers')
            pass
    if True:
# skip files in same directory with similar timestamps
        try:
            group = remove_close_times(group)
        except GetSerialError:
            pass
    if len(group) == 1:
        print ('Singular group')
        raise CurateException()
    if len(group) == 0:
        print ('Empty group')
        raise CurateException()
    group = sorted(group, key=lambda path: os.path.basename(path))
    return group


def path_get_serial(path):
    filename = os.path.basename(path)
    filename, ext = os.path.splitext(filename)
    if len(filename) == 8 and (filename[:4].lower() in ['dsc_', 'gopr', 'img_', 'dscn']):
        return int(filename[4:8])
    elif len(filename) == 28 and filename[20:24].lower() in ['dscn', 'dsc_']:
        return int(filename[24:28])
    elif len(filename) >= 22 and filename[:4].lower() == 'img_':
# Truncate timestamp to the minute
        #return int(filename[4:12]+filename[13:22])
        return int(filename[4:12]+filename[13:17])
    else:
        try:
            return int(filename)
        except ValueError:
            raise GetSerialError()


def remove_sequential(group):
    group = sorted(group)
    if not group:
        return []
    subset = [group[0]]
    last_serial = path_get_serial(group[0])
    for index, path in enumerate(group[1:]):
        serial_number = path_get_serial(path)
        print(serial_number)
        if serial_number - last_serial != 1:
            subset.append(path)
        else:
            print('Ignoring '+path)
        last_serial = serial_number

    return subset


def path_get_timestamp(path):
    filename = os.path.basename(path)
    filename, ext = os.path.splitext(filename)
    if len(filename) >= 22 and filename[:4].lower() == 'img_':
        timestamp = int(filename[4:12]+filename[13:22])
        print('timestamp:', timestamp)
        return timestamp

    raise GetSerialError()


def remove_close_times(group):
    group = sorted(group)
    if not group:
        return []
    subset = [group[0]]
    last_timestamp = path_get_timestamp(group[0])
    for index, path in enumerate(group[1:]):
        timestamp = path_get_timestamp(path)
        print ('difference', (timestamp - last_timestamp))
        if (timestamp - last_timestamp) < 100000:
            print('Ignoring '+path)
        else:
            subset.append(path)
        last_timestamp = timestamp

    return subset


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='reconcile output from the `findimagedupes` program')
    parser.add_argument('logfile')
    parser.add_argument('--skip-sequential', action='store_true', default=False)
    args = parser.parse_args()

    with open(args.logfile, 'r') as f:
        lines = f.readlines()

    cm = ConfigManager(args.logfile+'.ini')

    groups = []

    for line in lines:
        paths = line[0:-1].split(' /')
        paths = [paths[0]] + ['/'+path for path in paths[1:]]
        groups.append(paths)

    for group_i, group in enumerate(groups):
        if 'resume' in cm.config:
            if group_i < int(cm.config['resume']['group']):
                continue

        sys.stdout.write('group %d '%group_i)
        if len(group) > 100:
            print ('Group %d has %d files, skipping' % (group_i+1, len(group)))
            continue
        jpeginfo_d = {}
        exifinfo_d = {}
        try:
            group = curate_group(group)
        except CurateException:
            continue
        for path in group:
            if os.path.isfile(path):
                sys.stdout.write('.'); sys.stdout.flush()
                filesize = os.stat(path).st_size
                try:
                    img = PIL.Image.open(path)
                    width, height = img.size
                    exif = img._getexif() if img.format == 'JPEG' else None
                    if exif:
                        if 36867 in exif:
                            origdatetime = exif[36867]
                        elif 306 in exif:
                            origdatetime = exif[306]
                        else:
                            origdatetime = ''
                        if 37521 in exif:
                            origdatetime += ' '+exif[37521]
                    else:
                        origdatetime = ''
                    jpeginfo_d[path] = '%dx%d %s %d' % (width, height, origdatetime, filesize)
                    exifinfo_d[path] = {'origdatetime': origdatetime}
                except IOError:
                    jpeginfo_d[path] = '%d' % (filesize)
            else:
                sys.stdout.write('x')
        sys.stdout.write('\n')

        if len(group)==2 \
                and (group[0] in exifinfo_d and \
                     group[1] in exifinfo_d) \
                and (exifinfo_d[group[0]]['origdatetime'] == \
                     exifinfo_d[group[1]]['origdatetime']):
            target = 0
            while target < len(group):
                if 'Pictures/iPhoto/' in group[target]:
                    break
                if 'XT1254/bluetooth/' in group[target]:
                    break
                target += 1
            keep_target = 0 if target==1 else 1
            if target < len(group) and \
                    'Pictures/iPhoto' not in group[keep_target] and \
                    'XT1254/bluetooth/' not in group[keep_target]:
                max_path_len = max(map(len, group))
                for path in group:
                    print('%-*s %s' % (max_path_len, path, jpeginfo_d[path]))
                print('\nGoing to delete '+group[target])
                resp = raw_input('Does this look right? ')
                if resp.startswith('y'):
                    retval = os.system('gvfs-trash \'%s\'' % group[target])
                    if retval == 0:
                        del group[target]

        while True:
            try:
                group = curate_group(group, args.skip_sequential)
            except CurateException:
                break

            print ('%d files in group %d/%d:' % (len(group), group_i+1,
                                                 len(groups)))

            max_path_len = max(map(len, group))
            for index, path in enumerate(group):
# TODO this could be done faster by a module
                print ('%3d: %-*s %s (%s)' % (index,
                                         max_path_len,
                                         path,
                                         jpeginfo_d[path],
                                         format_size(os.path.getsize(path))))
            resp = raw_input('Action: ')
            if resp.startswith('d'):
                try:
                    select_index = int(resp[1:])
                except ValueError as e:
                    print (str(e))
                else:
                    print ('Deleting "%s"' % group[select_index])
                    retval = os.system('gvfs-trash \'%s\'' % group[select_index])
                    if retval == 0:
                        del group[select_index]
            elif resp.lower().startswith('c'):
                try:
                    select_index = int(resp[1:])
                except ValueError as e:
                    print (str(e))
                else:
                    oldpath = group[select_index]
                    jpg_name = oldpath.replace('.tiff', '.jpg')
                    jpg_name = jpg_name.replace('.tif', '.jpg')
                    print ('Converting "%s" to "%s"' % (oldpath, jpg_name))
                    retval = os.system('convert -quality 95 \'%s\' \'%s\'' % (oldpath, jpg_name))
                    if retval == 0:
                        retval2 = os.system('gvfs-trash \'%s\'' % oldpath)
                    #if not os.path.isfile(oldpath) and os.path.isfile(jpg_name):
                    if retval2 == 0:
                        jpeginfo_d[jpg_name] = jpeginfo_d[oldpath]
                        group[select_index] = jpg_name
                        del jpeginfo_d[oldpath]
            elif resp.lower().startswith('q'):
                raise KeyboardInterrupt
            elif resp.lower().startswith('n'):
                break
            elif resp.lower().startswith('v'):
                Popen(['eog']+group)
            elif resp.lower().startswith('ss'):
                args.skip_sequential = True
            else:
                print('Commands:')
                print('v: visualize')
                print('d[index]: delete file specified by index')
                print('c[index]: convert file specified by index to JPEG')
                print('n: proceed to next file group')
                print('ss: skip sequential files')
                print('q: quit')

        cm.config['resume'] = {'group': group_i}
        cm.save()
