import httpx

from .db import json_dump

class ModelConfigurationError(ValueError):
    pass

class ModelResponseError(ValueError):
    pass

def complete_json(settings, instruction, data, schema, *, timeout=20):
    if not all((settings.model_url, settings.model_name, settings.model_key)):
        raise ModelConfigurationError("模型地址、名称和密钥需要同时配置。")
    body = {"model": settings.model_name, "messages": [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json_dump(data)},
    ]}
    try:
        response = httpx.post(
            settings.model_url.rstrip("/") + "/chat/completions", json=body, timeout=timeout,
            headers={"Authorization": f"Bearer {settings.model_key}"},
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```") and raw.endswith("```") and "\n" in raw:
            raw = raw.split("\n", 1)[1][:-3]
        return schema.validate_json(raw)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, AttributeError, TypeError):
        raise ModelResponseError("模型服务未返回可校验的结果。") from None
