import api from './axios'
import { sseUrl } from './axios'

export const getChatHistory  = (pid: number) => api.get(`/ask/${pid}/history`).then(r => r.data)
export const clearHistory    = (pid: number) => api.delete(`/ask/${pid}/history`)

export function streamAsk(
  pid: number, question: string,
  onChunk: (c: string) => void,
  onDone: () => void,
  onReplace?: (c: string) => void,
) {
  const token = localStorage.getItem('bi_token') || ''
  fetch(`/api/ask/${pid}/send?token=${token}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  }).then(async res => {
    const reader = res.body!.getReader()
    const dec = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const d = JSON.parse(line.slice(6))
          if (d.chunk) onChunk(d.chunk)
          if (d.replace && onReplace) onReplace(d.replace)
          if (d.done) onDone()
        } catch { /* ignore */ }
      }
    }
    onDone()
  }).catch(() => onDone())
}
