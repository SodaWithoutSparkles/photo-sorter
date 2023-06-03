#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import logging
import os
from PIL import Image, UnidentifiedImageError
import datetime
from multiprocessing import Pool
import zipfile
from pathlib import Path

# optimization
from operator import itemgetter
from collections import deque

# init args
parser = argparse.ArgumentParser("photo sorter", formatter_class=argparse.RawTextHelpFormatter,
                                 description='sort photos based on different parameters')
parser.add_argument(
    "path", help="path to folder/directory where the photos are stored")
parser.add_argument('-v', '--verbose', action='count',
                    help="print debug info, use -vv to increase level to DEBUG", default=0)
parser.add_argument('-t', '--threshold',
                    help='change the threshold to group image, default is 3', default=3, metavar='SECONDS')
parser.add_argument('-p', '--package', action='store_true',
                    help="package the sorted photos to zip files")
parser.add_argument(
    '-e', '--export', help='path to store result, default to result.txt under the path given', metavar='PATH')
args = parser.parse_args()

# init logging formatter


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s [%(levelname).1s]: %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, '%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


def setupLogger():
    # DEBUG INFO WARN ERROR CRITICAL
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(args.verbose, len(levels) - 1)]
    logger = logging.getLogger("sorter")
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logger.setLevel(level)
    logger.addHandler(ch)
    # logging.basicConfig(
    #                 format='%(asctime)s [%(levelname)-8s]: %(message)s',
    #                 datefmt='%Y-%m-%d %H:%M:%S',
    #                 )
    return logger


def getFileList(path: str = args.path):
    if path[-1] != os.sep:
        path += os.sep
    logger.info(f'Scanning directory {path}')
    try:
        filenames = next(os.walk(path), (None, None, []))[2]
    except:
        logging.critical(f'unable to scan directory {path}, check permissions')
        exit(1)
    # filter away non-jpg files
    for filename in filenames:
        if not (filename.endswith('.JPG') or filename.endswith('.jpg')):
            filenames.remove(filename)
    # convert to relative path from current working dir
    fileList = [path + filename for filename in filenames]

    logger.info(f'Found {len(filenames)} files')
    return fileList


def getTimeShot(path):
    try:
        timeString = Image.open(path).getexif()
        timeString = timeString.get(306)
        # id 306: Exif.Image.DateTime
        # https://exiv2.org/tags.html
        unix = int(datetime.datetime.strptime(
            timeString, '%Y:%m:%d %H:%M:%S').timestamp())
        
    except UnidentifiedImageError as e:
        logger.warning(e)
        # it is not a image file, default to 1, which will be grouped together
        unix = 1
    except Exception as e:
        print(type(e))
        logger.warning(e)
        # cannot get unix timestamp, default to 0, which will be grouped together
        unix = 0
    return (path, unix)


def getTimeShotList(filenames):
    logger.info('Extracting creation date')
    p = Pool(4)
    return p.imap(getTimeShot, filenames, chunksize=4)


def sortPhotos(timeList):

    countList = [1]
    # get the number of photos that should be in the each group
    for n in range(len(timeList)-1):
        diffTime = timeList[n+1][1] - timeList[n][1]
        if diffTime <= args.threshold:
            countList[-1] += 1
        else:
            countList.append(1)

    # create list of groups
    photosList = []
    l = deque(timeList)
    for count in countList:
        # create a group of <size> in countList
        group = []
        for i in range(count):
            group.append(l.popleft()[0])

        photosList.append(group)

    return photosList


def packagePhotos(grouped):
    logger.info('Packaging files...')
    Path(args.path + os.sep + 'packaged').mkdir(parents=True, exist_ok=True)
    for item in grouped:
        zipPhotosInList(item)

def zipPhotosInList(filenames: list):
    # first item in the list is the creation timestamp of the first file
    # which will be used as the filename
    if args.path[-1] != os.sep:
        zipPath = args.path + os.sep + 'packaged' + os.sep + os.path.basename(filenames[0]) + '.zip'
    else:
        zipPath = args.path + 'packaged' + os.sep + os.path.basename(filenames[0]) + '.zip'
    logger.debug(f'Creating {zipPath}')
    with zipfile.ZipFile(zipPath, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in filenames:
            logger.debug(f'\tInserting file {filename}')
            zf.write(filename, arcname=os.path.basename(filename))
    return 0


def exportResult(grouped):
    if args.export == None:
        if args.path[-1] != os.sep:
            path = args.path + os.sep + 'result.txt'
        else:
            path = args.path + 'result.txt'
        writeResults(path, grouped)
    else:
        try:
            writeResults(args.export, grouped)
        except:
            logger.warn(
                f'unable to write to {args.export}, defaulting to default path')
            if path != os.sep:
                path = args.path + os.sep + 'result.txt'
            else:
                path = args.path + 'result.txt'
            writeResults(path, grouped)


def writeResults(path, grouped):
    logger.info(f'Writing result to {path}')
    with open(path, 'w') as f:
        for item in grouped:
            f.write(str(item)+'\n')


def main():
    filenames = getFileList()
    timeList = getTimeShotList(filenames)
    # sort based on the unix timestamp
    timeList = sorted(timeList, key=itemgetter(1))
    # group photos based on time diff
    grouped = sortPhotos(timeList)
    # write result to file
    exportResult(grouped)
    if args.package:
        packagePhotos(grouped)
    print('Done!')
    # for i in grouped:
    #     print(i)


if __name__ == '__main__':
    logger = setupLogger()
    main()
