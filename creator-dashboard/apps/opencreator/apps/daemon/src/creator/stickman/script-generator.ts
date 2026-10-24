import { z } from 'zod';

const scriptSegmentSchema = z.object({
  id: z.string().min(1),
  narration: z.string().min(1),
  visualPrompt: z.string().min(1),
  durationSeconds: z.number().positive().max(60)
}).strict();

const scriptSchema = z.object({
  title: z.string().min(1),
  segments: z.array(scriptSegmentSchema).min(1).max(24)
}).strict();

export type StickmanScript = z.infer<typeof scriptSchema>;
export type StickmanScriptSegment = z.infer<typeof scriptSegmentSchema>;

export function parseStickmanScript(value: unknown): StickmanScript {
  const parsed = scriptSchema.parse(value);
  const ids = new Set<string>();
  for (const segment of parsed.segments) {
    if (ids.has(segment.id)) throw new Error(`duplicate_script_segment: ${segment.id}`);
    ids.add(segment.id);
  }
  return parsed;
}

export async function generateStickmanScript(input: {
  baseUrl: string;
  apiKey: string;
  model: string;
  topic: string;
  targetDurationSeconds: number;
  fetchImpl?: typeof fetch;
}): Promise<StickmanScript> {
  const response = await (input.fetchImpl ?? fetch)(
    `${input.baseUrl.replace(/\/$/, '') || 'https://api.openai.com/v1'}/chat/completions`,
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${input.apiKey}`,
        'content-type': 'application/json'
      },
      body: JSON.stringify({
        model: input.model,
        stream: false,
        response_format: { type: 'json_object' },
        messages: [{
          role: 'user',
          content: [
            '为火柴人知识短视频生成严格 JSON 脚本。',
            '格式：{"title":"...","segments":[{"id":"s1","narration":"...","visualPrompt":"...","durationSeconds":5}]}。',
            `目标总时长约 ${input.targetDurationSeconds} 秒。主题：${input.topic}`
          ].join('\n')
        }]
      })
    }
  );
  if (!response.ok) throw new Error(`stickman_script_failed: HTTP ${response.status}`);
  const payload = await response.json() as { choices?: Array<{ message?: { content?: string } }> };
  const content = payload.choices?.[0]?.message?.content;
  if (!content) throw new Error('stickman_script_invalid_response');
  const cleanJson = extractJsonPayload(content);
  return parseStickmanScript(JSON.parse(cleanJson));
}

function extractJsonPayload(raw: string): string {
  const trimmed = raw.trim();
  const match = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (match && match[1]) return match[1].trim();
  const firstBrace = trimmed.indexOf('{');
  const lastBrace = trimmed.lastIndexOf('}');
  if (firstBrace !== -1 && lastBrace > firstBrace) return trimmed.slice(firstBrace, lastBrace + 1);
  return trimmed;
}
