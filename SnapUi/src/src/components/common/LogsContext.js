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

  const config = window.ENV;
  const pollingIntervalMs = 1000; // Poll every 1 second for more live updates

  const connectSSE = useCallback(() => {
    if (!username || eventSourceRef.current) return;
    
    const token = getCookie('token');
    if (!token) return;
    
    // Remove token from URL - EventSource will send cookies automatically
    const eventSource = new EventSource(`${config.apiUrl}/logs/stream`);
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      try {
        const logData = JSON.parse(event.data);
        
        // Skip keepalive messages
        if (logData.type === 'keepalive') return;
        
        // Check if we've already seen this log ID
        if (seenLogIds.has(logData.id)) return;
        
        // Add to seen IDs
        setSeenLogIds(prev => new Set([...prev, logData.id]));
        
        // Add new log
        setLogs(prev => {
          const updatedLogs = [...prev, logData];
          return updatedLogs.slice(-200); // Keep last 200 logs
        });
        
      } catch (error) {
        console.error('Error parsing SSE log data:', error);
      }
    };
    
    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      // Attempt to reconnect after a delay
      setTimeout(() => {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
          connectSSE();
        }
      }, 5000);
    };
    
  }, [username, config.apiUrl, seenLogIds]);

  const disconnectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
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
