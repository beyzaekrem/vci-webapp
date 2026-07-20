import argparse

from controller import Controller, argmods, trigger_box

parser = argparse.ArgumentParser(description="haha brrrr")
argmods.add_server_list_argument(parser)

args = parser.parse_args()

c = Controller(args.server, log_level="DEBUG", mode="observer")

print("connected.")
input("\nSwitch? [Enter]")

c.switch_mode("ring_buffer")

input("Start? [Enter]")

trigger_box("on")
c.start()


input("Stop? [Enter]")

trigger_box("off")
c.stop()
