import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import { getCookie } from "../../utils/cookies";

const LogsContext = createContext();

export const useLogs = () => useContext(LogsContext);

export const LogsProvider = ({ children }) => {
  const [logs, setLogs] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [username, setUsername] = useState(null);
  const [loading, setLoading] = useState(false);
  const pollingInterval = useRef(null);
  const recentLogHashes = useRef(new Set());
  const lastLogTimestamp = useRef(null);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const eventSourceRef = useRef(null);
  const [seenLogIds, setSeenLogIds] = useState(new Set());
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;
  const reconnectTimeoutRef = useRef(null);

  const config = window.ENV;
  const pollingIntervalMs = 1000; // Poll every 1 second for more live updates

  const connectSSE = useCallback(() => {
    if (!username) {
      console.log('[LogsContext] Cannot connect SSE: username not set');
      return;
    }
    
    console.log('[LogsContext] Attempting to connect SSE for user:', username);
    
    // Don't create a new connection if one already exists and is open/connecting
    if (eventSourceRef.current) {
      const readyState = eventSourceRef.current.readyState;
      if (readyState === EventSource.CONNECTING || readyState === EventSource.OPEN) {
        console.log('[LogsContext] SSE already connected/connecting, readyState:', readyState);
        return; // Already connected or connecting
      }
      // Clean up closed/failed connection
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    const token = getCookie('token');
    if (!token) {
      console.warn('[LogsContext] No token available for SSE connection');
      return;
    }
    
    try {
      // Clear any pending reconnect timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      // Reset reconnect attempts on successful connection
      reconnectAttemptsRef.current = 0;
      
      // EventSource doesn't support custom headers, so we need to pass token as query param
      // The backend will try cookies first, then fall back to query param
      const sseUrl = `${config.apiUrl}/logs/stream?token=${encodeURIComponent(token)}`;
      console.log('[LogsContext] Creating SSE connection to:', sseUrl.replace(token, 'TOKEN_HIDDEN'));
      
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;
      
      eventSource.onopen = () => {
        // Connection opened successfully
        reconnectAttemptsRef.current = 0;
        setLoading(true);
        console.log('[LogsContext] SSE connection opened successfully');
      };
      
      eventSource.onmessage = (event) => {
        try {
          const logData = JSON.parse(event.data);
          
          // Skip keepalive messages
          if (logData.type === 'keepalive') {
            // console.log('[LogsContext] Received keepalive');
            return;
          }
          
          // Validate required fields
          if (!logData.id || !logData.message) {
            console.warn('[LogsContext] Invalid log data received (missing id or message):', logData);
            return;
          }
          
          // Check for duplicates using both ID and content hash
          // Create a content hash for duplicate detection (message + timestamp + initiator)
          const contentHash = `${logData.message}-${logData.timestamp}-${logData.initiator || 'unknown'}`;
          
          setSeenLogIds(prev => {
            // Check both ID and content hash to catch duplicates even if ID changes
            if (prev.has(logData.id) || prev.has(`content:${contentHash}`)) {
              // Duplicate detected, skip silently
              return prev;
            }
            
            // Add both ID and content hash to seen set
            const newSeenIds = new Set([...prev, logData.id, `content:${contentHash}`]);
            
            // Clean up old content hashes to prevent memory bloat (keep last 500)
            if (newSeenIds.size > 1000) {
              // Remove oldest content hashes (those starting with "content:")
              const contentHashes = Array.from(newSeenIds).filter(id => id.startsWith('content:'));
              const ids = Array.from(newSeenIds).filter(id => !id.startsWith('content:'));
              // Keep only recent content hashes
              const recentContentHashes = contentHashes.slice(-500);
              return new Set([...ids, ...recentContentHashes]);
            }
            
            // Add new log
            setLogs(prevLogs => {
              // Also check if this exact log already exists in the current logs array
              const isDuplicate = prevLogs.some(log => 
                log.message === logData.message && 
                log.timestamp === logData.timestamp && 
                log.initiator === logData.initiator
              );
              
              if (isDuplicate) {
                return prevLogs;
              }
              
              const updatedLogs = [...prevLogs, logData];
              return updatedLogs.slice(-200); // Keep last 200 logs
            });
            
            return newSeenIds;
          });
          
        } catch (error) {
          console.error('Error parsing SSE log data:', error, event.data);
        }
      };
      
      eventSource.onerror = (error) => {
        const readyState = eventSource.readyState;
        console.error('[LogsContext] SSE error event:', {
          readyState,
          readyStateName: readyState === EventSource.CONNECTING ? 'CONNECTING' : 
                         readyState === EventSource.OPEN ? 'OPEN' : 
                         readyState === EventSource.CLOSED ? 'CLOSED' : 'UNKNOWN',
          error,
          url: eventSource.url
        });
        
        if (readyState === EventSource.CLOSED) {
          // Connection closed, attempt to reconnect
          eventSourceRef.current = null;
          
          // Only reconnect if we haven't exceeded max attempts
          if (reconnectAttemptsRef.current < maxReconnectAttempts && username) {
            reconnectAttemptsRef.current += 1;
            const delay = Math.min(5000 * reconnectAttemptsRef.current, 30000); // Exponential backoff, max 30s
            
            console.log(`[LogsContext] SSE connection closed. Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})...`);
            
            reconnectTimeoutRef.current = setTimeout(() => {
              if (username && !eventSourceRef.current) {
                connectSSE();
              }
            }, delay);
          } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
            console.error('[LogsContext] SSE connection failed after maximum reconnect attempts');
            setLoading(false);
          }
        } else if (readyState === EventSource.CONNECTING) {
          // Still connecting, wait a bit
          console.log('[LogsContext] SSE connection in progress...');
        } else {
          // Other error states
          console.error('[LogsContext] SSE connection error:', error, 'ReadyState:', readyState);
        }
      };
      
    } catch (error) {
      console.error('Error creating SSE connection:', error);
      eventSourceRef.current = null;
      setLoading(false);
    }
    
  }, [username, config.apiUrl]);

  const disconnectSSE = useCallback(() => {
    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    // Reset reconnect attempts
    reconnectAttemptsRef.current = 0;
    
    if (eventSourceRef.current) {
      try {
        eventSourceRef.current.close();
      } catch (error) {
        console.warn('Error closing SSE connection:', error);
      }
      eventSourceRef.current = null;
    }
    setLoading(false);
  }, []);

  const fetchContainerLogs = useCallback(async () => {
    if (!username) return;
    
    try {
      const response = await fetch(`${config.apiUrl}/logs/container`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${getCookie('token')}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        console.error('Failed to fetch container logs:', response.statusText);
        return;
      }
      
      const data = await response.json();
      
      if (data.logs && Array.isArray(data.logs)) {
        // Convert container logs to our log format
        const newLogs = data.logs.map(log => ({
          id: `container-${log.timestamp}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp: log.timestamp,
          message: log.message,
          type: log.level || 'info',
          initiator: log.initiator || 'SnapApi',
          cluster: 'default',
          rawLine: log.raw_line || log.message
        }));
        
        setLogs(prev => {
          // Find new logs by comparing timestamps
          let newLogsToAdd = [];
          
          if (lastLogTimestamp.current === null) {
            // First time - add all logs
            newLogsToAdd = newLogs;
            if (newLogs.length > 0) {
              lastLogTimestamp.current = newLogs[newLogs.length - 1].timestamp;
            }
          } else {
            // Find logs newer than our last timestamp
            const lastTimestampIndex = newLogs.findIndex(log => 
              log.timestamp === lastLogTimestamp.current
            );
            
            if (lastTimestampIndex !== -1) {
              // Add logs after the last known timestamp
              newLogsToAdd = newLogs.slice(lastTimestampIndex + 1);
            } else {
              // If we can't find the exact timestamp, add the last few logs
              newLogsToAdd = newLogs.slice(-5);
            }
            
            if (newLogsToAdd.length > 0) {
              lastLogTimestamp.current = newLogsToAdd[newLogsToAdd.length - 1].timestamp;
            }
          }
          
          if (newLogsToAdd.length > 0) {
            // Add new logs to existing ones
            const updatedLogs = [...prev, ...newLogsToAdd];
            
            // Keep only the last 200 logs to prevent memory issues
            return updatedLogs.slice(-200);
          }
          
          return prev;
        });
      }
    } catch (error) {
      console.error('Error fetching container logs:', error);
    }
  }, [username, config.apiUrl]);

  const startPolling = useCallback(() => {
    // Only use SSE for all log updates (existing + new)
    // This eliminates duplicates caused by using both polling and SSE
    connectSSE();
    
    setLoading(true);
  }, [connectSSE]);

  const stopPolling = useCallback(() => {
    // Stop SSE connection
    disconnectSSE();
    
    setLoading(false);
  }, [disconnectSSE]);

  useEffect(() => {
    if (!username) {
      stopPolling();
      return;
    }

    startPolling();
    return () => {
      stopPolling();
    };
  }, [username, startPolling, stopPolling]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnectSSE();
    };
  }, [disconnectSSE]);

  const addLog = (log, cluster = 'default', initiator = 'User') => {
    const timestamp = new Date().toLocaleTimeString();
    const newLog = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp,
      message: log,
      type: 'info',
      cluster,
      initiator
    };
    setLogs(prev => {
      // Create a hash for duplicate detection
      const logHash = `${log}-info-${initiator}`;
      
      // Check if this exact log was recently added
      if (recentLogHashes.current.has(logHash)) {
        return prev;
      }
      
      // Add to recent hashes
      recentLogHashes.current.add(logHash);
      
      return [...prev, newLog];
    });
  };

  const addErrorLog = (log, cluster = 'default', initiator = 'User') => {
    const timestamp = new Date().toLocaleTimeString();
    const newLog = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp,
      message: log,
      type: 'error',
      cluster,
      initiator
    };
    setLogs(prev => {
      // Create a hash for duplicate detection
      const logHash = `${log}-error-${initiator}`;
      
      // Check if this exact log was recently added
      if (recentLogHashes.current.has(logHash)) {
        return prev;
      }
      
      // Add to recent hashes
      recentLogHashes.current.add(logHash);
      
      return [...prev, newLog];
    });
  };

  const addSuccessLog = (log, cluster = 'default', initiator = 'User') => {
    const timestamp = new Date().toLocaleTimeString();
    const newLog = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp,
      message: log,
      type: 'success',
      cluster,
      initiator
    };
    setLogs(prev => {
      // Create a hash for duplicate detection
      const logHash = `${log}-success-${initiator}`;
      
      // Check if this exact log was recently added
      if (recentLogHashes.current.has(logHash)) {
        return prev;
      }
      
      // Add to recent hashes
      recentLogHashes.current.add(logHash);
      
      return [...prev, newLog];
    });
  };

  const clearLogs = async () => {
    setLogs([]);
    recentLogHashes.current.clear();
    lastLogTimestamp.current = null;
    setShouldAutoScroll(true);
    setSeenLogIds(new Set()); // Reset seen log IDs
    
    // Also clear logs on the server side
    try {
      await fetch(`${config.apiUrl}/logs/clear`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${getCookie('token')}`,
          'Content-Type': 'application/json'
        }
      });
    } catch (error) {
      console.error('Error clearing server logs:', error);
    }
  };

  const toggleLogs = () => {
    setIsOpen(prev => !prev);
  };

  const openLogs = () => {
    setIsOpen(true);
  };

  const closeLogs = () => {
    setIsOpen(false);
  };

  const startTracking = () => setLoading(true);
  const stopTracking = () => setLoading(false);


  return (
    <LogsContext.Provider value={{ 
      logs, 
      isOpen, 
      loading,
      shouldAutoScroll,
      setShouldAutoScroll,
      addLog, 
      addErrorLog, 
      addSuccessLog, 
      clearLogs, 
      toggleLogs, 
      openLogs, 
      closeLogs,
      setUsername,
      startTracking,
      stopTracking
    }}>
      {children}
    </LogsContext.Provider>
  );
};
