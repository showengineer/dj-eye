import unittest
from prodj.network.packets import BeatPacket, DBField, DBMessage
from construct import Container

class PacketsTestCase(unittest.TestCase):
    def test_absolute_position_pitch_is_signed_centi_percent(self):
        data = (
            b"Qspt1WmJOL" +
            b"\x0b" +
            b"CDJ-3000\x00" + (b"\x00" * 11) +
            b"\x01\x00" +
            b"\x03" +
            b"\x00" +
            b"\x3c" +
            b"\x00\x00\x00\xb4" +
            b"\x00\x01\x13\xb1" +
            b"\xff\xff\xff\xfb" +
            b"\x00" * 8 +
            b"\x00\x00\x05\x00"
        )

        packet = BeatPacket.parse(data)

        self.assertEqual(packet.type, "type_absolute_position")
        self.assertEqual(packet.player_number, 3)
        self.assertEqual(packet.content.playhead, 70577)
        self.assertAlmostEqual(packet.content.pitch, 0.9995)

    def test_string_parsing(self):
        self.assertEqual(
            DBField.parse(
                b"\x26\x00\x00\x00\x0a\xff\xfa\x00\x48\x00\x49\x00" +
                b"\x53\x00\x54\x00\x4f\x00\x52\x00\x59\xff\xfb\x00\x00"
            ),
            Container(type='string')(value="\ufffaHISTORY\ufffb"),
        )

        self.assertEqual(
            DBField.parse(
                b"\x26\x00\x00\x00\x0b\xff\xfa\x00\x50\x00\x4c\x00" +
                b"\x41\x00\x59\x00\x4c\x00\x49\x00\x53\x00\x54\xff\xfb" +
                b"\x00\x00"
            ),
            Container(type='string')(value="\ufffaPLAYLIST\ufffb"),
        )

        self.assertEqual(
            DBField.parse(bytes([
                0x26, 0x00, 0x00, 0x00, 0x09, 0xff, 0xfa, 0x00, 0x41,
                0x00, 0x52, 0x00, 0x54, 0x00, 0x49, 0x00, 0x53,
                0x00, 0x54, 0xff, 0xfb, 0x00, 0x00,
            ])),
            Container(type='string')(value="\ufffaARTIST\ufffb"))

    def test_building_root_menu_request_menu_item_part(self):
        data = bytes([
            0x11, 0x87, 0x23, 0x49, 0xae,
            0x11, 0x05, 0x80, 0x00, 0x01,
            0x10, 0x41, 0x01,
            0x0f, 0x0c, 0x14, 0x00, 0x00, 0x00, 0x0c, 0x06, 0x06, 0x06, 0x02,
            0x06, 0x02, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x16,
            0x11, 0x00, 0x00, 0x00, 0x14,
            0x26, 0x00, 0x00, 0x00, 0x09, 0xff, 0xfa, 0x00, 0x41,
            0x00, 0x52, 0x00, 0x54, 0x00, 0x49, 0x00, 0x53,
            0x00, 0x54, 0xff, 0xfb, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x02,
            0x26, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x95,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
        ])

        message = DBMessage.parse(data)

        self.assertEqual(message.type, 'menu_item')
        self.assertEqual(
            message,
            (Container
                (magic=2267236782)
                (transaction_id=92274689)
                (type='menu_item')
                (argument_count=12)
                (arg_types=[
                    'int32', 'int32', 'int32', 'string', 'int32', 'string',
                    'int32', 'int32', 'int32', 'int32', 'int32', 'int32',
                ])
                (args=[
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=22),
                    Container(type='int32')(value=20),
                    Container(type='string')(value='\ufffaARTIST\ufffb'),
                    Container(type='int32')(value=2),
                    Container(type='string')(value=''),
                    Container(type='int32')(value=149),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                ])
             )
        )
