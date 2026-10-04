"""AI 网关 Mock（成员1 真实网关就位前，member-3 先对着它并行开发）.

约定与真实网关一致：chat(prompt) -> str
第2周末只需把这里换成真实调用，答疑代码不用改。
"""
import os


def gateway_chat(prompt: str) -> str:
    # 预留真实网关开关：有 Key 且显式打开才调真实接口
    if os.getenv("USE_REAL_LLM") == "1":
        try:
            from openai import OpenAI  # 可选依赖，未安装则回落 Mock
            client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY", ""),
                base_url=os.getenv(
                    "DASHSCOPE_BASE_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
            )
            r = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "qwen-plus"),
                messages=[{"role": "user", "content": prompt}],
            )
            return r.choices[0].message.content
        except Exception as e:
            return f"[真实网关失败，已降级Mock] {e} | 针对「{prompt[:50]}」的通用回答：请咨询活动主办方。"
    return f"[Mock回答] 针对「{prompt[:80]}」：活动时间地点以活动详情页为准，综测加分见活动说明，报名问题请联系主办方。"
