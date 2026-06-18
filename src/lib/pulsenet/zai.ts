import ZAI from 'z-ai-web-dev-sdk'

// Singleton ZAI instance — created once, reused across requests.
let _zai: Awaited<ReturnType<typeof ZAI.create>> | null = null

export async function getZai() {
  if (!_zai) _zai = await ZAI.create()
  return _zai
}

/** Single-shot LLM completion with a system + user message. */
export async function llmComplete(systemPrompt: string, userPrompt: string): Promise<string> {
  try {
    const zai = await getZai()
    const completion = await zai.chat.completions.create({
      messages: [
        { role: 'assistant', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ],
      thinking: { type: 'disabled' },
    })
    return completion.choices[0]?.message?.content ?? ''
  } catch (err) {
    console.error('[llmComplete] failed:', (err as Error).message)
    return ''
  }
}

/** Web search via the z-ai function API. */
export async function webSearch(query: string, num = 8) {
  try {
    const zai = await getZai()
    return (await zai.functions.invoke('web_search', { query, num })) as Array<{
      url: string
      name: string
      snippet: string
      host_name: string
      date: string
    }>
  } catch (err) {
    console.error('[webSearch] failed:', (err as Error).message)
    return []
  }
}

/** Tolerant JSON-array parser: strips markdown fences and extracts the first [ ... ] block. */
export function parseJsonArray<T = unknown>(raw: string): T[] {
  if (!raw) return []
  let t = raw.trim()
  t = t.replace(/^```(?:json)?/i, '').replace(/```\s*$/i, '').trim()
  const start = t.indexOf('[')
  const end = t.lastIndexOf(']')
  if (start === -1 || end === -1 || end < start) return []
  try {
    return JSON.parse(t.slice(start, end + 1)) as T[]
  } catch {
    return []
  }
}
