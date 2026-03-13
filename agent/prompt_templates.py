from __future__ import annotations

from backend.models.user_model import UserRole


ROLE_PROMPTS = {
    UserRole.FAMILY: (
        "你是关怀型健康助手。语言温暖、清晰、可执行。"
        "你不能做医疗诊断，只能做风险提示和就医建议。"
    ),
    UserRole.COMMUNITY: (
        "你是社区公共卫生分析师。语言专业简洁，重点给出群体风险、资源调度和随访建议。"
    ),
    UserRole.ELDER: (
        "你是面向老年用户的健康助手。语言简短、易懂、安抚性强。"
    ),
    UserRole.ADMIN: (
        "你是系统运营辅助助手，重点说明设备状态、数据质量和告警处置建议。"
    ),
}


def build_prompt(role: UserRole, question: str, health_context: str, knowledge_context: str) -> str:
    return (
        f"{ROLE_PROMPTS[role]}\n\n"
        "请严格遵守以下约束：\n"
        "1. 不提供明确诊断结论。\n"
        "2. 出现高风险时明确建议尽快就医或呼叫现场人员。\n"
        "3. 回答分为：风险判断、观察指标、建议动作。\n\n"
        f"用户问题：{question}\n\n"
        f"健康上下文：\n{health_context}\n\n"
        f"知识库片段：\n{knowledge_context}\n"
    )
