/**
 * AI helpers used by the legacy TS pipeline (ingest.ts / ripple.ts).
 *
 * This module previously used the z-ai-web-dev-sdk (sandbox-only).
 * It now uses @google/generative-ai (public) with GEMINI_API_KEY_A.
 *
 * In normal operation the FastAPI engine handles all ingestion.
 * This file only runs when the engine is offline (graceful fallback).
 */

import { GoogleGenerativeAI } from '@google/generative-ai'

// --- LLM ---

let _genAI: GoogleGenerativeAI | null = null

function getGenAI(): GoogleGenerativeAI | null {
  const key = process.env.GEMINI_API_KEY_A ?? process.env.GEMINI_API_KEY ?? ''
  if (!key) return null
  if (!_genAI) _genAI = new GoogleGenerativeAI(key)
  return _genAI
}

/** Single-shot LLM completion with a system + user message. */
export async function llmComplete(systemPrompt: string, userPrompt: string): Promise<string> {
  try {
    const genAI = getGenAI()
    if (!genAI) return ''
    const model = genAI.getGenerativeModel({
      model: process.env.GEMINI_MODEL ?? 'gemini-2.5-flash',
      systemInstruction: systemPrompt,
    })
    const result = await model.generateContent(userPrompt)
    return result.response.text() ?? ''
  } catch (err) {
    console.error('[llmComplete] failed:', (err as Error).message)
    return ''
  }
}

/**
 * Web search — returns empty in the TS fallback path.
 *
 * The Python engine handles search via RSS feeds (GDACS, ReliefWeb, GDELT).
 * When running TS-only, only the USGS structured feed works without a search key.
 * Add a Serper/Tavily/Bing key to SEARCH_API_KEY to enable search in fallback mode.
 */
export async function webSearch(
  query: string,
  _num = 8,
): Promise<Array<{ url: string; name: string; snippet: string; host_name: string; date: string }>> {
  // Placeholder: swap this for your preferred search provider if needed.
  const apiKey = process.env.SEARCH_API_KEY ?? ''
  if (!apiKey) return []
  // Example: Serper.dev
  try {
    const res = await fetch('https://google.serper.dev/search', {
      method: 'POST',
      headers: { 'X-API-KEY': apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: query, num: _num }),
    })
    if (!res.ok) return []
    const data = await res.json() as { organic?: Array<{ title: string; link: string; snippet: string }> }
    return (data.organic ?? []).map((r) => ({
      url: r.link ?? '',
      name: r.title ?? '',
      snippet: r.snippet ?? '',
      host_name: new URL(r.link ?? 'https://unknown').hostname,
      date: '',
    }))
  } catch {
    return []
  }
}

/** Tolerant JSON-array parser: strips markdown fences, extracts the first [...] block. */
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
