import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";

const LogsContext = createContext();

export const useLogs = () => useContext(LogsContext);

export const LogsProvider = ({ children }) => {
  const [logs, setLogs] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [username, setUsername] = useState(null);
  const [loading, setLoading] = useState(false);
  const pingTimeout = useRef(null);
  const reconnectTimeout = useRef(null);
  const recentLogHashes = useRef(new Set());
  const socketRef = useRef(null);

  const config = window.ENV;
  const pingInterval = 10000;

  const connectWebSocket = useCallback(() => {
    if (!username) return;
    
    // Prevent multiple connections
    if (socketRef.current && socketRef.current.readyState === WebSocket.CONNECTING) {
      console.log("WebSocket already connecting, skipping...");
      return;
    }
    
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      console.log("WebSocket already connected, skipping...");
      return;
    }
    
    const ws = new WebSocket(`${config.wsUrl}/ws/progress/${username}`);
    console.log("Connecting to WebSocket for logs...", username);

    ws.onopen = () => {
      console.log("Connected to WebSocket for logs");
      startPing(ws);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "pong") {
        console.log("Received pong from server");
        return;
      }

      if (data.type === "progress") {
        // Convert progress data to log format
        const logType = data.progress === "failed" ? "error" : 
                       data.progress === 100 ? "success" : "info";
        
        // Parse the message to extract timestamp and clean message
        let logMessage = data.message || `${data.task_name || "Task"} - Progress: ${data.progress}%`;
        let serverTimestamp = null;
        
        // Check if message contains server timestamp (format: "YYYY-MM-DD HH:MM:SS \nmessage")
        const timestampMatch = logMessage.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \n(.+)$/);
        if (timestampMatch) {
          serverTimestamp = timestampMatch[1];
          logMessage = timestampMatch[2];
        }
        
        // Use server timestamp if available, otherwise use current time
        const timestamp = serverTimestamp || new Date().toLocaleTimeString();
        const newLog = {
          id: `ws-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp,
          message: logMessage,
          type: logType,
          taskName: data.task_name,
          progress: data.progress,
          cluster: data.cluster || 'default',
          initiator: data.initiator || 'SnapApi'
        };
        
        setLogs(prev => {
          // Create a hash for duplicate detection
          const logHash = `${logMessage}-${logType}-${data.task_name}`;
          
          // Check if this exact log was recently added
          if (recentLogHashes.current.has(logHash)) {
            console.log("Duplicate log prevented:", logMessage);
            return prev;
          }
          
          // Add to recent hashes and clean old ones
          recentLogHashes.current.add(logHash);
          
          // Keep only last 20 hashes to prevent memory leak
          if (recentLogHashes.current.size > 20) {
            const hashesArray = Array.from(recentLogHashes.current);
            recentLogHashes.current.clear();
            hashesArray.slice(-10).forEach(hash => recentLogHashes.current.add(hash));
          }
          
          return [...prev, newLog];
        });
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected. Attempting to reconnect...");
      stopPing();
      // Use a longer delay to prevent rapid reconnection loops
      reconnectTimeout.current = setTimeout(() => {
        if (username) { // Only reconnect if username still exists
          connectWebSocket();
        }
      }, 10000); // Increased delay to 10 seconds
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      ws.close();
    };

    socketRef.current = ws;
  }, [username, config.wsUrl]);

  const startPing = (ws) => {
    pingTimeout.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
        console.log("Sent ping to server"); 
      }
    }, pingInterval);
  };

  const stopPing = () => {
    if (pingTimeout.current) clearInterval(pingTimeout.current);
  };

  useEffect(() => {
    if (!username) return;

    connectWebSocket();
    return () => {
      if (socketRef.current) socketRef.current.close();
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      stopPing();
    };
  }, [username, connectWebSocket]);

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

  const clearLogs = () => {
    setLogs([]);
    recentLogHashes.current.clear();
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
