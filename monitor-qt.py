#!/usr/bin/env python3

import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette
from PyQt5.QtCore import Qt
import signal
import argparse

from prodj.core.prodj import ProDj
from prodj.gui.gui import Gui
from prodj.audio.output import OutputConfig, format_output_devices
from prodj.timecode.ltc_service import LTCService

def arg_size(value):
  number = int(value)
  if number < 1000 or number > 60000:
    raise argparse.ArgumentTypeError("%s is not between 1000 and 60000".format(value))
  return number

def arg_layout(value):
  if value not in ["xy", "yx", "xx", "yy", "row", "column"]:
    raise argparse.ArgumentTypeError("%s is not a value from the list xy, yx, xx, yy, row or column".format(value))
  return value

def arg_player_slots(value):
  number = int(value)
  if number not in [4, 6]:
    raise argparse.ArgumentTypeError("%s is not 4 or 6".format(value))
  return number

parser = argparse.ArgumentParser(description='Python ProDJ Link')
provider_group = parser.add_mutually_exclusive_group()
provider_group.add_argument('--disable-pdb', dest='enable_pdb', action='store_false', help='Disable PDB provider')
provider_group.add_argument('--disable-dbc', dest='enable_dbc', action='store_false', help='Disable DBClient provider')
parser.add_argument('--color-preview', action='store_true', help='Show NXS2 colored preview waveforms')
parser.add_argument('--color-waveform', action='store_true', help='Show NXS2 colored big waveforms')
parser.add_argument('-c', '--color', action='store_true', help='Shortcut for --color-preview and --color-waveform')
parser.add_argument('-q', '--quiet', action='store_const', dest='loglevel', const=logging.WARNING, help='Only display warning messages', default=logging.INFO)
parser.add_argument('-d', '--debug', action='store_const', dest='loglevel', const=logging.DEBUG, help='Display verbose debugging information')
parser.add_argument('--dump-packets', action='store_const', dest='loglevel', const=0, help='Dump packet fields for debugging', default=logging.INFO)
parser.add_argument('--chunk-size', dest='chunk_size', help='Chunk size of NFS downloads (high values may be faster but fail on some networks)', type=arg_size, default=None)
parser.add_argument('-f', '--fullscreen', action='store_true', help='Start with fullscreen window')
parser.add_argument('-l', '--layout', dest='layout', help='Display layout, values are xy (default), yx, xx, yy, row or column', type=arg_layout, default="xy")
parser.add_argument('--player-slots', type=arg_player_slots, default=4, help='Show a fixed number of player sections, either 4 or 6')
parser.add_argument('--vcdj-player', type=int, default=None, help='Virtual CDJ player number, defaults to player-slots + 1')
parser.add_argument('--list-audio-devices', action='store_true', help='List audio output devices and exit')
parser.add_argument('--ltc-player', type=int, default=None, help='Generate LTC from this player number')
parser.add_argument('--ltc-device', type=int, default=None, help='Audio output device index for LTC')
parser.add_argument('--ltc-channel', type=int, default=0, help='Zero-based output channel for LTC')
parser.add_argument('--ltc-fps', type=float, default=25, help='LTC frame rate')
parser.add_argument('--ltc-sample-rate', type=int, default=48000, help='LTC audio sample rate')
parser.add_argument('--ltc-blocksize', type=int, default=512, help='LTC audio callback block size')
parser.add_argument('--ltc-volume', type=float, default=0.8, help='LTC output volume')
parser.add_argument('--ltc-compensation-ms', type=float, default=0, help='Generate LTC this many milliseconds ahead to compensate fixed output latency')
parser.add_argument('--ltc-buffer-ms', type=float, default=120, help='Target producer buffer for LTC audio')

args = parser.parse_args()

logging.basicConfig(level=args.loglevel, format='%(levelname)-7s %(module)s: %(message)s')

if args.list_audio_devices:
  print(format_output_devices())
  raise SystemExit(0)

prodj = ProDj()
prodj.data.pdb_enabled = args.enable_pdb
prodj.data.dbc_enabled = args.enable_dbc
if args.chunk_size is not None:
  prodj.nfs.setDownloadChunkSize(args.chunk_size)
app = QApplication([])
gui = Gui(
  prodj,
  show_color_waveform=args.color_waveform or args.color,
  show_color_preview=args.color_preview or args.color,
  arg_layout=args.layout,
  player_slots=args.player_slots,
)
if args.fullscreen:
  gui.setWindowState(Qt.WindowFullScreen | Qt.WindowMaximized | Qt.WindowActive)

pal = app.palette()
pal.setColor(QPalette.Window, Qt.black)
pal.setColor(QPalette.Base, Qt.black)
pal.setColor(QPalette.Button, Qt.black)
pal.setColor(QPalette.WindowText, Qt.white)
pal.setColor(QPalette.Text, Qt.white)
pal.setColor(QPalette.ButtonText, Qt.white)
pal.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.gray)
app.setPalette(pal)

signal.signal(signal.SIGINT, lambda s,f: app.quit())

prodj.set_client_keepalive_callback(gui.keepalive_callback)
prodj.set_client_change_callback(gui.client_change_callback)
prodj.set_media_change_callback(gui.media_callback)
prodj.start()
vcdj_player = args.vcdj_player if args.vcdj_player is not None else args.player_slots + 1
prodj.vcdj_set_player_number(vcdj_player)
prodj.vcdj_enable()

ltc = None
if args.ltc_player is not None:
  ltc_config = OutputConfig(
    device=args.ltc_device,
    sample_rate=args.ltc_sample_rate,
    channels=args.ltc_channel + 1,
    blocksize=args.ltc_blocksize,
  )
  ltc = LTCService(
    prodj,
    args.ltc_player,
    output_config=ltc_config,
    output_channel=args.ltc_channel,
    fps=args.ltc_fps,
    volume=args.ltc_volume,
    latency_compensation_ms=args.ltc_compensation_ms,
    target_buffer_ms=args.ltc_buffer_ms,
  )
  ltc.start()

app.exec()
logging.info("Shutting down...")
if ltc is not None:
  ltc.stop()
prodj.stop()
