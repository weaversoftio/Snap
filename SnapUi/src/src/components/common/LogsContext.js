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
  const lastLogCount = useRef(0);

  const config = window.ENV;
  const pollingIntervalMs = 2000; // Poll every 2 seconds

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
          // Only add new logs (avoid duplicates)
          const currentLogCount = newLogs.length;
          if (currentLogCount <= lastLogCount.current) {
            return prev;
          }
          
          // Get only the new logs
          const newLogsToAdd = newLogs.slice(lastLogCount.current);
          lastLogCount.current = currentLogCount;
          
          // Add new logs to existing ones
          const updatedLogs = [...prev, ...newLogsToAdd];
          
          // Keep only the last 100 logs to prevent memory issues
          return updatedLogs.slice(-100);
        });
      }
    } catch (error) {
      console.error('Error fetching container logs:', error);
    }
  }, [username, config.apiUrl]);

  const startPolling = useCallback(() => {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
    }
    
    // Initial fetch
    fetchContainerLogs();
    
    // Set up polling
    pollingInterval.current = setInterval(() => {
      fetchContainerLogs();
    }, pollingIntervalMs);
    
    setLoading(true);
  }, [fetchContainerLogs]);

  const stopPolling = useCallback(() => {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
      pollingInterval.current = null;
    }
    setLoading(false);
  }, []);

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
    lastLogCount.current = 0;
    
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
