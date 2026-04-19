import { useCallback, useEffect, useRef, useState } from 'react'
import { wsUrl } from '../api/axios'
import { useDebounce } from './useDebounce'

interface PresenceUser { user_id: number; full_name: string; color: string; locked: boolean }

export function useSectionSocket(sectionId: number | null) {
  const ws = useRef<WebSocket | null>(null)
  const [content, setContent]       = useState('')
  const [presence, setPresence]     = useState<PresenceUser[]>([])
  const [lockHolder, setLockHolder] = useState<PresenceUser | null>(null)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving'>('saved')
  const isEditing = useRef(false)

  useEffect(() => {
    if (!sectionId) return
    const socket = new WebSocket(wsUrl(`/section/${sectionId}`))
    ws.current = socket

    socket.onmessage = ev => {
      const msg = JSON.parse(ev.data)
      switch (msg.type) {
        case 'init':
          setContent(msg.content)
          setPresence(msg.users || [])
          setLockHolder(msg.lock_holder || null)
          break
        case 'text_broadcast':
          if (!isEditing.current) setContent(msg.content)
          break
        case 'presence_update':
          setPresence(msg.users || [])
          setLockHolder(msg.lock_holder || null)
          break
        case 'save_ack':
          setSaveStatus('saved')
          break
      }
    }

    const ping = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' }))
    }, 20_000)

    return () => { clearInterval(ping); socket.close(); ws.current = null }
  }, [sectionId])

  const _sendUpdate = useCallback((c: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'text_change', content: c }))
      setSaveStatus('saving')
    }
  }, [])

  const sendUpdate = useDebounce(_sendUpdate, 300)

  const handleChange = useCallback((c: string) => {
    setContent(c)
    sendUpdate(c)
  }, [sendUpdate])

  const requestLock = useCallback(() => {
    isEditing.current = true
    ws.current?.send(JSON.stringify({ type: 'lock_request', section_id: sectionId }))
  }, [sectionId])

  const releaseLock = useCallback(() => {
    isEditing.current = false
    ws.current?.send(JSON.stringify({ type: 'lock_release', section_id: sectionId }))
  }, [sectionId])

  return { content, handleChange, presence, lockHolder, saveStatus, requestLock, releaseLock }
}
