import React from "react";
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
  Terminal
} from "@mui/icons-material";
import { useLogs } from "./LogsContext";

const LogsSection = () => {
  const { logs, isOpen, clearLogs, toggleLogs, loading } = useLogs();

  const getLogColor = (type) => {
    switch (type) {
      case 'error':
        return '#f44336';
      case 'warning':
        return '#ff9800';
      case 'success':
        return '#4caf50';
      default:
        return '#666666';
    }
  };

  const formatLogLine = (log) => {
    // Format similar to podman logs: timestamp message
    const timestamp = log.timestamp || new Date().toLocaleString();
    const message = log.message || '';
    
    // Color code based on log level
    const color = getLogColor(log.type);
    
    return { timestamp, message, color };
  };

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1300, // Higher than Material-UI drawer (1200)
        backgroundColor: '#f5f5f5',
        borderTop: '2px solid #e0e0e0',
        maxHeight: isOpen ? '300px' : '60px',
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
          backgroundColor: '#e3f2fd',
          borderBottom: isOpen ? '1px solid #ddd' : 'none',
          cursor: 'pointer',
          minHeight: '48px'
        }}
        onClick={toggleLogs}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Terminal color="primary" />
          <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#1976d2' }}>
            Container Logs
          </Typography>
          {logs.length > 0 && (
            <Chip 
              label={logs.length} 
              size="small" 
              color="primary" 
              variant="outlined"
            />
          )}
          {loading && (
            <Chip 
              icon={<Wifi />}
              label="Live" 
              size="small" 
              color="success" 
              variant="outlined"
            />
          )}
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {isOpen && logs.length > 0 && (
            <Button
              size="small"
              startIcon={<ClearAll />}
              onClick={(e) => {
                e.stopPropagation();
                clearLogs();
              }}
              sx={{ textTransform: 'none' }}
            >
              Clear
            </Button>
          )}
          <IconButton size="small">
            {isOpen ? <ExpandMore /> : <ExpandLess />}
          </IconButton>
        </Box>
      </Box>

      {/* Logs Content */}
      <Collapse in={isOpen} timeout="auto" unmountOnExit>
        <Box
          sx={{
            maxHeight: '240px',
            overflowY: 'auto',
            backgroundColor: '#1e1e1e', // Dark terminal background
            color: '#ffffff',
            fontFamily: 'monospace',
            fontSize: '0.8rem',
            p: 1
          }}
        >
          {logs.length > 0 ? (
            <Box sx={{ whiteSpace: 'pre-wrap' }}>
              {logs.slice(-100).map((log, index) => {
                const { timestamp, message, color } = formatLogLine(log);
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
                        color: '#888',
                        minWidth: '140px',
                        mr: 1,
                        flexShrink: 0
                      }}
                    >
                      {timestamp}
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
                color: '#888'
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
