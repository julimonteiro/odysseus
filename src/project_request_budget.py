"""Final local request budget, including rendered tool schemas and chat template."""
import json
from urllib.parse import urlsplit
from src.context_compactor import trim_for_context
from src.model_context import estimate_tokens


async def fit_local_request(client, url, model, messages, tools, context, max_tokens=0, headers=None):
    parts=urlsplit(url)
    if parts.hostname not in {'localhost','127.0.0.1','::1'} or not context:
        return messages, max_tokens
    root=f'{parts.scheme}://{parts.netloc}'
    reserve=min(max(int(max_tokens or 1024),128), max(128,context//4))
    target=context-reserve-128
    current=messages
    # llama.cpp can render/tokenize exactly; other local providers use a
    # conservative fallback including schemas, never messages alone.
    async def count(items):
        payload={'model':model,'messages':items,'tools':tools or [],'add_generation_prompt':True}
        r=await client.post(root+'/apply-template',json=payload,headers=headers,timeout=3)
        r.raise_for_status();prompt=r.json()['prompt']
        r=await client.post(root+'/tokenize',json={'model':model,'content':prompt,'add_special':False},headers=headers,timeout=3)
        r.raise_for_status();return len(r.json()['tokens'])
    try:
        for _ in range(5):
            actual=await count(current)
            if actual<=target:
                return current,reserve
            budget=max(64,int(estimate_tokens(current)*target/actual*.8))
            current=trim_for_context(current,budget,reserve_tokens=0)
        raise ValueError('Local request cannot fit the model context with its current tool schemas. Use fewer tools or a larger context window.')
    except (KeyError,TypeError,json.JSONDecodeError):
        pass
    except ValueError:
        raise
    except Exception:
        pass
    schema_cost=int(len(json.dumps(tools or [],ensure_ascii=False))*.6)+512
    available=target-schema_cost
    if available<256:
        raise ValueError('Tool schemas exceed the local model context budget. Enable fewer tools.')
    current=trim_for_context(current,max(64,int(available*.65)),reserve_tokens=0)
    if estimate_tokens(current)/.65 + schema_cost > target:
        raise ValueError('Protected context and tool schemas cannot fit this local model. Reduce attached context or use a larger window.')
    return current,reserve
