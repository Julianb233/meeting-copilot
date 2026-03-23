import { useEffect, useState } from 'react'
import zoomSdk from '@zoom/appssdk'

type ZoomStatus = 'connecting' | 'connected' | 'error' | 'standalone'

interface ZoomMeetingContext {
  meetingTopic?: string
  meetingID?: string
}

interface UseZoomContextReturn {
  zoomStatus: ZoomStatus
  meetingContext: ZoomMeetingContext | null
  isInMeeting: boolean
}

export function useZoomContext(): UseZoomContextReturn {
  const [zoomStatus, setZoomStatus] = useState<ZoomStatus>('connecting')
  const [meetingContext, setMeetingContext] = useState<ZoomMeetingContext | null>(null)

  useEffect(() => {
    async function initZoom() {
      try {
        const configResponse = await zoomSdk.config({
          capabilities: [
            'getMeetingContext',
            'getUserContext',
            'getRunningContext',
            'expandApp',
            'onMeeting',
            'openUrl',
          ],
        })
        console.log('Zoom SDK configured:', configResponse)
        setZoomStatus('connected')

        const runningContext = await zoomSdk.getRunningContext()
        console.log('Zoom running context:', runningContext)

        if (runningContext.context === 'inMeeting') {
          const ctx = await zoomSdk.getMeetingContext()
          setMeetingContext(ctx as unknown as ZoomMeetingContext)
        }
      } catch (err) {
        console.log('Not running inside Zoom, standalone mode:', err)
        setZoomStatus('standalone')
      }
    }
    initZoom()
  }, [])

  const isInMeeting = zoomStatus === 'connected' && meetingContext !== null

  return { zoomStatus, meetingContext, isInMeeting }
}
