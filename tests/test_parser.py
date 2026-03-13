from ai.data_generator import SyntheticHealthDataGenerator
from iot.parser import T10PacketParser


def test_parser_merges_dual_packets() -> None:
    generator = SyntheticHealthDataGenerator(device_count=1)
    sample = generator.next_sample()
    packet_a, packet_b = generator.encode_packet_pair(sample)

    parser = T10PacketParser()
    assert parser.feed(sample.device_mac, packet_a) is None
    decoded = parser.feed(sample.device_mac, packet_b)

    assert decoded is not None
    assert decoded.device_mac == sample.device_mac
    assert decoded.heart_rate == sample.heart_rate
    assert decoded.temperature == sample.temperature
    assert decoded.blood_oxygen == sample.blood_oxygen
    assert decoded.blood_pressure == sample.blood_pressure
