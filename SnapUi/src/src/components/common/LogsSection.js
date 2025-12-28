import React, { useRef, useEffect } from "react";
import {
  Box,
  Typography,
  IconButton,
  Paper,
  Collapse,
  Button,
  Chip,
  TextField,
  InputAdornment
} from "@mui/material";
import {
  ExpandLess,
  ExpandMore,
  ClearAll,
  BugReport,
  Wifi,
  Terminal,
  Download
} from "@mui/icons-material";
import { useLogs } from "./LogsContext";
import consoleLogger from "../../utils/consoleLogger";

const LogsSection = () => {
  const { logs, isOpen, clearLogs, toggleLogs, loading, shouldAutoScroll, setShouldAutoScroll } = useLogs();
  const logsContainerRef = useRef(null);
  const isUserScrolling = useRef(false);

  const getLogColor = (type) => {
    switch (type) {
      case 'error':
        return '#f44336';
      case 'warning':
        return '#ff9800';
      case 'success':
        return '#4caf50';
      default:
        return '#ffffff';
    }
  };

  const formatLogLine = (log) => {
    // Format similar to podman logs: timestamp message
    const timestamp = log.timestamp || new Date().toLocaleString();
    const message = log.message || '';
    
    // Color code based on log level
    const color = getLogColor(log.type);
    
    // Get component color
    const componentColor = getComponentColor(log.initiator);
    
    return { timestamp, message, color, componentColor, initiator: log.initiator };
  };

  const getComponentColor = (initiator) => {
    switch (initiator) {
      case 'SnapApi':
        return '#2196f3'; // Blue
      case 'SnapWatcher':
        return '#4caf50'; // Green
      case 'SnapHook':
        return '#ff9800'; // Orange
      default:
        return '#ffffff'; // White
    }
  };

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (shouldAutoScroll && logsContainerRef.current && !isUserScrolling.current) {
      const container = logsContainerRef.current;
      container.scrollTop = container.scrollHeight;
    }
  }, [logs, shouldAutoScroll]);

  // Handle scroll events to detect user scrolling
  const handleScroll = (e) => {
    const container = e.target;
    const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 5;
    
    if (isAtBottom) {
      setShouldAutoScroll(true);
      isUserScrolling.current = false;
    } else {
      setShouldAutoScroll(false);
      isUserScrolling.current = true;
    }
  };

  // Reset user scrolling flag when logs section is opened/closed
  useEffect(() => {
    if (isOpen) {
      isUserScrolling.current = false;
      setShouldAutoScroll(true);
    }
  }, [isOpen, setShouldAutoScroll]);

  // Download logs function
  const handleDownloadLogs = (e) => {
    e.stopPropagation();
    
    try {
      // Get last 10 browser console logs
      const browserLogs = consoleLogger.getLastLogs(10);
      
      // Get last 10 SnapApi logs (filter by initiator === 'SnapApi')
      const snapApiLogs = logs
        .filter(log => log.initiator === 'SnapApi')
        .slice(-10);
      
      // Format logs for text file
      let logContent = '=== SNAP LOGS EXPORT ===\n';
      logContent += `Generated: ${new Date().toISOString()}\n\n`;
      
      // Browser Console Logs Section
      logContent += '=== BROWSER CONSOLE LOGS (Last 10) ===\n';
      if (browserLogs.length > 0) {
        browserLogs.forEach(log => {
          logContent += `[${log.timestamp}] [${log.level.toUpperCase()}] ${log.message}\n`;
        });
      } else {
        logContent += 'No browser console logs available.\n';
      }
      
      logContent += '\n';
      
      // SnapApi Logs Section
      logContent += '=== SNAPAPI LOGS (Last 10) ===\n';
      if (snapApiLogs.length > 0) {
        snapApiLogs.forEach(log => {
          const timestamp = log.timestamp || new Date().toLocaleString();
          const type = log.type || 'info';
          const message = log.message || '';
          logContent += `[${timestamp}] [${type.toUpperCase()}] [${log.initiator || 'SnapApi'}] ${message}\n`;
        });
      } else {
        logContent += 'No SnapApi logs available.\n';
      }
      
      // Create blob and download
      const blob = new Blob([logContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `snap-logs-${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading logs:', error);
    }
  };

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'fixed',
        bottom: 0,
        left: '240px', // Start after the sidebar drawer
        right: 0,
        zIndex: 1300, // Higher than Material-UI drawer (1200)
        backgroundColor: '#e5e7eb',
        borderTop: '2px solid rgba(0, 0, 0, 0.1)',
        borderRadius: '16px 16px 0 0',
        maxHeight: isOpen ? '300px' : '44px',
        transition: 'max-height 0.3s ease-in-out',
        overflow: 'hidden'
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 1,
          backgroundColor: '#e5e7eb',
          borderBottom: isOpen ? '1px solid rgba(0, 0, 0, 0.1)' : 'none',
          cursor: 'pointer',
          minHeight: '44px',
          height: '44px'
        }}
        onClick={toggleLogs}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Terminal sx={{ color: '#374151' }} />
          <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#111827' }}>
            Logs
          </Typography>
          {logs.length > 0 && (
            <Chip 
              label={logs.length} 
              size="small" 
              color="primary" 
              variant="outlined"
              sx={{ borderColor: 'rgba(0, 0, 0, 0.2)', color: '#374151' }}
            />
          )}
          {loading && (
            <Chip 
              icon={<Wifi />}
              label="Live" 
              size="small" 
              color="success" 
              variant="outlined"
              sx={{ borderColor: 'rgba(0, 0, 0, 0.2)', color: '#374151' }}
            />
          )}
          {!shouldAutoScroll && (
            <Chip 
              label="Manual Scroll" 
              size="small" 
              color="warning" 
              variant="outlined"
              sx={{ borderColor: 'rgba(0, 0, 0, 0.2)', color: '#374151' }}
            />
          )}
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Button
            size="small"
            startIcon={<Download />}
            onClick={handleDownloadLogs}
            sx={{ textTransform: 'none', color: '#374151' }}
            title="Download last 10 browser console logs and 10 SnapApi logs"
          >
            Download Logs
          </Button>
          {isOpen && logs.length > 0 && (
            <Button
              size="small"
              startIcon={<ClearAll />}
              onClick={(e) => {
                e.stopPropagation();
                clearLogs();
              }}
              sx={{ textTransform: 'none', color: '#374151' }}
            >
              Clear
            </Button>
          )}
          {isOpen && !shouldAutoScroll && (
            <Button
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                setShouldAutoScroll(true);
                isUserScrolling.current = false;
                if (logsContainerRef.current) {
                  logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
                }
              }}
              sx={{ textTransform: 'none', color: '#374151' }}
            >
              Scroll to Bottom
            </Button>
          )}
          <IconButton size="small" sx={{ color: '#374151' }}>
            {isOpen ? <ExpandMore /> : <ExpandLess />}
          </IconButton>
        </Box>
      </Box>

      {/* Logs Content */}
      <Collapse in={isOpen} timeout="auto" unmountOnExit>
        <Box
          ref={logsContainerRef}
          onScroll={handleScroll}
          sx={{
            maxHeight: '240px',
            overflowY: 'auto',
            backgroundColor: '#1e1e1e', // Dark terminal background
            color: '#ffffff',
            fontFamily: 'monospace',
            fontSize: '0.8rem',
            p: 1,
            scrollBehavior: 'smooth'
          }}
        >
          {logs.length > 0 ? (
            <Box sx={{ whiteSpace: 'pre-wrap' }}>
              {logs.slice(-100).map((log, index) => {
                const { timestamp, message, color, componentColor, initiator } = formatLogLine(log);
                return (
                  <Box
                    key={log.id || index}
                    sx={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      mb: 0.5,
                      '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.1)'
                      }
                    }}
                  >
                    <Box
                      sx={{
                        color: 'white',
                        minWidth: '140px',
                        mr: 1,
                        flexShrink: 0
                      }}
                    >
                      {timestamp}
                    </Box>
                    <Box
                      sx={{
                        color: componentColor,
                        minWidth: '100px',
                        mr: 1,
                        flexShrink: 0,
                        fontWeight: 'bold'
                      }}
                    >
                      {initiator}:
                    </Box>
                    <Box
                      sx={{
                        color: color,
                        wordBreak: 'break-word',
                        flex: 1
                      }}
                    >
                      {message}
                    </Box>
                  </Box>
                );
              })}
            </Box>
          ) : (
            <Box
              sx={{
                p: 3,
                textAlign: 'center',
                color: '#ffffff'
              }}
            >
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                No logs available. Container activity will appear here.
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default LogsSection;
