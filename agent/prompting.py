from __future__ import annotations

from backend.models.user_model import UserRole


ROLE_PROMPTS = {
    UserRole.FAMILY: "你是面向家属的健康陪伴助手，语气温和、清晰，重点解释风险与下一步动作。",
    UserRole.COMMUNITY: "你是社区康养分析助手，重点输出群体风险分层、重点对象和调度建议。",
    UserRole.ELDER: "你是面向老人本人的健康助手，表达简短易懂，先安抚情绪，再给出可执行建议。",
    UserRole.ADMIN: "你是平台运维与业务联动助手，兼顾健康风险、设备在线状态和数据质量。",
}

SCOPE_PROMPTS = {
    "device": "当前任务是分析单台设备在一段时间内的监测数据，必须关注趋势、波动区间和关键异常。",
    "community": "当前任务是分析社区内多台设备在一段时间内的汇总数据，必须关注风险分层、重点对象与随访资源调度。",
}

FORMAT_GUIDE = {
    "device": "请按以下结构作答：1. 综合风险判断 2. 指标趋势解读 3. 关键异常与可能诱因 4. 建议动作 5. 后续观察重点。",
    "community": "请按以下结构作答：1. 社区总体态势 2. 高风险与中风险对象 3. 群体趋势与共性问题 4. 资源调度建议 5. 后续随访计划。",
}


def build_prompt_package(
    *,
    role: UserRole,
    scope: str,
    question: str,
    analysis_context: str,
    knowledge_context: str,
) -> dict[str, str]:
    scope_key = scope if scope in SCOPE_PROMPTS else "device"
    system = "\n".join(
        [
            ROLE_PROMPTS.get(role, ROLE_PROMPTS[UserRole.FAMILY]),
            SCOPE_PROMPTS[scope_key],
            "你不能做医疗诊断，但必须进行风险提示，并在高风险时明确建议尽快联系家属、社区值守人员或医生。",
            "必须优先依据提供的数据分析结果回答，不要忽略时间窗口、趋势、风险标记和建议动作。",
            FORMAT_GUIDE[scope_key],
        ]
    )
    user = (
        f"用户问题：{question.strip() or '请根据最近一段时间的监测数据给出完整分析。'}\n\n"
        f"结构化数据分析结果：\n{analysis_context}\n\n"
        f"知识库补充：\n{knowledge_context or '暂无匹配知识库片段。'}\n\n"
        "请使用中文回答，并结合数据窗口、异常事件、趋势变化和可执行建议进行完整说明。"
    )
    return {"system": system, "user": user}
