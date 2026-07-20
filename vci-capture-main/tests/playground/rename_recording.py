import argparse

from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD

parser = argparse.ArgumentParser()
parser.add_argument("old_name", type=str)
parser.add_argument("new_name", type=str)

args = parser.parse_args()

old_name = args.old_name
new_name = args.new_name

PERSISTENT_RECORD.rename_recording(old_name, new_name)
