from __future__ import annotations

from pathlib import Path

from agent.agent_service import HealthAgentService
from agent.rag_service import RAGService
from ai.anomaly_detector import CommunityHealthClusterer, IntelligentAnomalyScorer, RealtimeAnomalyDetector
from ai.data_generator import SyntheticHealthDataGenerator
from ai.health_score_model import BaselineTracker, HealthScoreService
from backend.config import get_settings
from backend.models.device_model import DeviceRecord
from backend.models.health_model import HealthSample, IngestResponse
from backend.services.alarm_service import AlarmService
from backend.services.device_service import DeviceService
from backend.services.stream_service import StreamService
from backend.services.websocket_manager import WebSocketManager
from iot.parser import T10PacketParser


_settings = get_settings()
_device_service = DeviceService()
_stream_service = StreamService(retention_points=_settings.stream_retention_points)
_websocket_manager = WebSocketManager()
_realtime_detector = RealtimeAnomalyDetector(
    window_size=_settings.realtime_window_size,
    zscore_threshold=_settings.zscore_threshold,
)
_alarm_service = AlarmService(detector=_realtime_detector)
_baseline_tracker = BaselineTracker()
_health_score_service = HealthScoreService(floor=_settings.health_score_floor)
_community_clusterer = CommunityHealthClusterer()
_intelligent_scorer = IntelligentAnomalyScorer()
_data_generator = SyntheticHealthDataGenerator(
    device_count=_settings.mock_device_count,
    mac_prefix=_settings.allowed_mac_prefixes[0],
)
_parser = T10PacketParser(sos_window_seconds=_settings.sos_broadcast_window_seconds)
_rag_service = RAGService(Path("docs") / "knowledge-base")
_agent_service = HealthAgentService(_settings, _rag_service)

_device_service.seed_devices(_data_generator.build_devices())


def get_device_service() -> DeviceService:
    return _device_service


def get_stream_service() -> StreamService:
    return _stream_service


def get_alarm_service() -> AlarmService:
    return _alarm_service


def get_websocket_manager() -> WebSocketManager:
    return _websocket_manager


def get_data_generator() -> SyntheticHealthDataGenerator:
    return _data_generator


def get_settings_dependency():
    return _settings


def get_parser() -> T10PacketParser:
    return _parser


def get_agent_service() -> HealthAgentService:
    return _agent_service


def get_intelligent_scorer() -> IntelligentAnomalyScorer:
    return _intelligent_scorer


def get_community_clusterer() -> CommunityHealthClusterer:
    return _community_clusterer


async def ingest_sample(sample: HealthSample) -> IngestResponse:
    device = _device_service.ensure_device(sample.device_mac, device_name=_settings.default_device_name)
    if not isinstance(device, DeviceRecord):
        raise RuntimeError("设备注册失败")

    baseline = _baseline_tracker.observe(sample)
    sample.health_score = _health_score_service.score(sample, baseline)
    _stream_service.publish(sample)
    alarms = _alarm_service.evaluate(sample)

    await _websocket_manager.broadcast_health(sample.device_mac, sample.model_dump(mode="json"))
    for alarm in alarms:
        await _websocket_manager.broadcast_alarm(alarm.model_dump(mode="json"))

    return IngestResponse(sample=sample, triggered_alarm_ids=[alarm.id for alarm in alarms])
