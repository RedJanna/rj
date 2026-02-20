from __future__ import annotations


def build_openai_response_fn(*, client, model_getter, system_prompt_getter, get_conversation_history_fn):
    async def get_openai_response(phone: str, message: str) -> str:
        try:
            history = get_conversation_history_fn(phone) if phone else []
            messages = [{"role": "system", "content": system_prompt_getter()}]
            messages.extend(history)
            messages.append({"role": "user", "content": message})
            completion = client.chat.completions.create(
                model=model_getter(),
                messages=messages,
                max_tokens=500,
                temperature=0.7,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ OpenAI hatası: {e}")
            return f"Hata: {e}"

    return get_openai_response
