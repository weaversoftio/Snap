import React from "react";
import {
  Box,
  Typography,
  IconButton,
  Paper,
  Collapse,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from "@mui/material";
import {
  ExpandLess,
  ExpandMore,
  ClearAll,
  BugReport,
  Wifi
} from "@mui/icons-material";
import { useLogs } from "./LogsContext";

const LogsSection = () => {
  const { logs, isOpen, clearLogs, toggleLogs, loading } = useLogs();

  const getLogColor = (type) => {
    switch (type) {
      case 'error':
        return '#f44336';
      case 'success':
        return '#4caf50';
      default:
        return '#2196f3';
    }
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
          <BugReport color="primary" />
          <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#1976d2' }}>
            System Logs
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
            backgroundColor: '#ffffff'
          }}
        >
          {logs.length > 0 ? (
            <TableContainer>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 'bold', backgroundColor: '#f5f5f5' }}>Time</TableCell>
                    <TableCell sx={{ fontWeight: 'bold', backgroundColor: '#f5f5f5' }}>Cluster</TableCell>
                    <TableCell sx={{ fontWeight: 'bold', backgroundColor: '#f5f5f5' }}>Initiator</TableCell>
                    <TableCell sx={{ fontWeight: 'bold', backgroundColor: '#f5f5f5' }}>Type</TableCell>
                    <TableCell sx={{ fontWeight: 'bold', backgroundColor: '#f5f5f5' }}>Task</TableCell>
                    <TableCell sx={{ fontWeight: 'bold', backgroundColor: '#f5f5f5' }}>Message</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {logs.slice(-50).reverse().map((log) => (
                    <TableRow
                      key={log.id}
                      sx={{
                        '&:hover': {
                          backgroundColor: '#f8f9fa'
                        }
                      }}
                    >
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {log.timestamp}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.8rem' }}>
                        {log.cluster || 'default'}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.8rem' }}>
                        {log.initiator || 'SnapApi'}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={log.type}
                          size="small"
                          sx={{
                            backgroundColor: getLogColor(log.type),
                            color: 'white',
                            fontSize: '0.7rem',
                            height: '20px'
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.8rem' }}>
                        {log.taskName || 'Unknown'}
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.8rem', wordBreak: 'break-word' }}>
                        {log.message}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Box
              sx={{
                p: 3,
                textAlign: 'center',
                color: '#666'
              }}
            >
              <Typography variant="body2">
                No logs available. System activity will appear here.
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default LogsSection;
