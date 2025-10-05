import React, { useState, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  IconButton,
  Collapse,
  Chip,
  Grid,
  Divider,
  Tooltip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Paper,
  LinearProgress,
  Avatar,
  Stack
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  ContentCopy as CopyIcon,
  Download as DownloadIcon,
  Storage as StorageIcon,
  Memory as MemoryIcon,
  NetworkCheck as NetworkIcon,
  Schedule as ScheduleIcon,
  Computer as ComputerIcon,
  Security as SecurityIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  DataObject as DataObjectIcon,
  Settings as SettingsIcon,
  Timeline as TimelineIcon,
  Folder as FolderIcon
} from '@mui/icons-material';
import { useSnackbar } from 'notistack';

const BeautifulAnalysisResults = ({ data, open, onClose, title = "Analysis Results" }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [expandedSections, setExpandedSections] = useState({});
  const [exportDialogOpen, setExportDialogOpen] = useState(false);

  // Dynamic section generation based on data structure
  const dynamicSections = useMemo(() => {
    if (!data) return {};
    
    const sections = {};
    const processedData = Array.isArray(data) ? data : [data];
    
    processedData.forEach((item, index) => {
      if (typeof item === 'object' && item !== null) {
        Object.keys(item).forEach(key => {
          const sectionKey = `${index}_${key}`;
          sections[sectionKey] = true; // Default to expanded
        });
      }
    });
    
    return sections;
  }, [data]);

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    enqueueSnackbar('Copied to clipboard!', { variant: 'success' });
  };

  // Dynamic data type detection and formatting
  const formatValue = (value, key = '') => {
    if (value === null || value === undefined) return 'N/A';
    
    // Check if it's a number (including strings that represent numbers)
    if (typeof value === 'number' || (!isNaN(value) && !isNaN(parseFloat(value)))) {
      const num = typeof value === 'number' ? value : parseFloat(value);
      
      // Check if it looks like bytes (size-related keys)
      if (key.toLowerCase().includes('size') || key.toLowerCase().includes('bytes')) {
        return formatBytes(num);
      }
      
      // Check if it looks like a percentage
      if (key.toLowerCase().includes('percent') || key.toLowerCase().includes('ratio')) {
        return `${num}%`;
      }
      
      // Check if it looks like a timestamp
      if (key.toLowerCase().includes('time') || key.toLowerCase().includes('date') || key.toLowerCase().includes('created') || key.toLowerCase().includes('updated')) {
        return formatDate(value);
      }
      
      return num.toLocaleString();
    }
    
    // Check if it's a date string
    if (typeof value === 'string' && (value.includes('T') || value.includes('-') || value.includes('/'))) {
      const date = new Date(value);
      if (!isNaN(date.getTime())) {
        return formatDate(value);
      }
    }
    
    // Check if it's a boolean
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    
    // Check if it's an array
    if (Array.isArray(value)) {
      return `${value.length} items`;
    }
    
    // Check if it's an object
    if (typeof value === 'object') {
      return `${Object.keys(value).length} properties`;
    }
    
    return String(value);
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch (e) {
      return dateString;
    }
  };

  // Smart categorization of fields
  const categorizeField = (key, value) => {
    const keyLower = key.toLowerCase();
    
    // Container/System related
    if (keyLower.includes('container') || keyLower.includes('pod') || keyLower.includes('name') || keyLower.includes('image')) {
      return { category: 'container', icon: <ComputerIcon color="primary" />, color: 'primary' };
    }
    
    // Size/Storage related
    if (keyLower.includes('size') || keyLower.includes('bytes') || keyLower.includes('memory') || keyLower.includes('storage')) {
      return { category: 'storage', icon: <StorageIcon color="primary" />, color: 'secondary' };
    }
    
    // Network related
    if (keyLower.includes('ip') || keyLower.includes('network') || keyLower.includes('port') || keyLower.includes('url')) {
      return { category: 'network', icon: <NetworkIcon color="primary" />, color: 'info' };
    }
    
    // Time related
    if (keyLower.includes('time') || keyLower.includes('date') || keyLower.includes('created') || keyLower.includes('updated')) {
      return { category: 'time', icon: <ScheduleIcon color="primary" />, color: 'warning' };
    }
    
    // Status related
    if (keyLower.includes('status') || keyLower.includes('state') || keyLower.includes('running') || keyLower.includes('active')) {
      return { category: 'status', icon: <CheckCircleIcon color="primary" />, color: 'success' };
    }
    
    // Configuration related
    if (keyLower.includes('config') || keyLower.includes('setting') || keyLower.includes('runtime') || keyLower.includes('engine')) {
      return { category: 'config', icon: <SettingsIcon color="primary" />, color: 'default' };
    }
    
    // Default category
    return { category: 'general', icon: <DataObjectIcon color="primary" />, color: 'default' };
  };

  const getStatusIcon = (value) => {
    const valueStr = String(value).toLowerCase();
    if (valueStr.includes('running') || valueStr.includes('active') || valueStr.includes('success')) {
      return <CheckCircleIcon color="success" />;
    }
    if (valueStr.includes('warning') || valueStr.includes('pending')) {
      return <WarningIcon color="warning" />;
    }
    if (valueStr.includes('error') || valueStr.includes('failed') || valueStr.includes('stopped')) {
      return <ErrorIcon color="error" />;
    }
    return <InfoIcon color="info" />;
  };

  const renderMetricCard = (title, value, icon, color = 'primary', subtitle = null) => (
    <Card sx={{ height: '100%', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
      <CardContent sx={{ textAlign: 'center', p: 2 }}>
        <Avatar sx={{ bgcolor: 'rgba(255,255,255,0.2)', mb: 1, mx: 'auto' }}>
          {icon}
        </Avatar>
        <Typography variant="h6" component="div" sx={{ fontWeight: 'bold', mb: 0.5 }}>
          {title}
        </Typography>
        <Typography variant="h4" component="div" sx={{ fontWeight: 'bold', mb: subtitle ? 0.5 : 0 }}>
          {value}
        </Typography>
        {subtitle && (
          <Typography variant="body2" sx={{ opacity: 0.8 }}>
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );

  const renderSectionHeader = (title, icon, isExpanded, onToggle) => (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        p: 2,
        cursor: 'pointer',
        backgroundColor: 'rgba(0,0,0,0.02)',
        borderRadius: 1,
        '&:hover': {
          backgroundColor: 'rgba(0,0,0,0.04)',
        },
      }}
      onClick={onToggle}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {icon}
        <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
          {title}
        </Typography>
      </Box>
      <IconButton>
        {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
      </IconButton>
    </Box>
  );

  const renderKeyValuePair = (key, value, type = 'string') => {
    const formattedValue = formatValue(value, key);
    const isStatusField = key.toLowerCase().includes('status') || key.toLowerCase().includes('state');
    
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', py: 0.5, gap: 2 }}>
        <Typography variant="body2" sx={{ fontWeight: 'medium', color: 'text.secondary', minWidth: '120px' }}>
          {key}:
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
          {isStatusField && getStatusIcon(value)}
          <Typography variant="body2" sx={{ fontWeight: 'bold', textAlign: 'left' }}>
            {formattedValue}
          </Typography>
          <Tooltip title="Copy to clipboard">
            <IconButton size="small" onClick={() => copyToClipboard(String(value))}>
              <CopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    );
  };

  // Dynamic rendering of nested objects
  const renderNestedObject = (obj, parentKey = '') => {
    if (!obj || typeof obj !== 'object') return null;
    
    return Object.entries(obj).map(([key, value]) => {
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        const sectionKey = `${parentKey}_${key}`;
        const isExpanded = expandedSections[sectionKey] !== false;
        const fieldInfo = categorizeField(key, value);
        
        return (
          <Card key={sectionKey} sx={{ mb: 2 }}>
            {renderSectionHeader(
              key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' '),
              fieldInfo.icon,
              isExpanded,
              () => toggleSection(sectionKey)
            )}
            <Collapse in={isExpanded}>
              <CardContent>
                {renderNestedObject(value, sectionKey)}
              </CardContent>
            </Collapse>
          </Card>
        );
      } else {
        return (
          <Box key={`${parentKey}_${key}`}>
            {renderKeyValuePair(key, value)}
          </Box>
        );
      }
    });
  };

  // Dynamic rendering of arrays
  const renderArray = (arr, key) => {
    if (!Array.isArray(arr)) return null;
    
    return (
      <Box sx={{ mt: 1 }}>
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
          {key} ({arr.length} items)
        </Typography>
        {arr.map((item, index) => (
          <Paper key={index} sx={{ p: 2, mb: 1, backgroundColor: 'rgba(0,0,0,0.02)' }}>
            {typeof item === 'object' && item !== null ? (
              renderNestedObject(item, `${key}_${index}`)
            ) : (
              <Typography variant="body2">{formatValue(item, key)}</Typography>
            )}
          </Paper>
        ))}
      </Box>
    );
  };

  // Main dynamic renderer
  const renderDynamicContent = () => {
    if (!data) return null;
    
    const processedData = Array.isArray(data) ? data : [data];
    
    return processedData.map((item, index) => {
      if (typeof item === 'object' && item !== null) {
        return (
          <Card key={index} sx={{ mb: 2 }}>
            {renderSectionHeader(
              `Data Section ${index + 1}`,
              <DataObjectIcon color="primary" />,
              expandedSections[`section_${index}`] !== false,
              () => toggleSection(`section_${index}`)
            )}
            <Collapse in={expandedSections[`section_${index}`] !== false}>
              <CardContent>
                {Object.entries(item).map(([key, value]) => {
                  if (Array.isArray(value)) {
                    return (
                      <Box key={key} sx={{ mb: 2 }}>
                        {renderArray(value, key)}
                      </Box>
                    );
                  } else if (typeof value === 'object' && value !== null) {
                    const sectionKey = `section_${index}_${key}`;
                    const isExpanded = expandedSections[sectionKey] !== false;
                    const fieldInfo = categorizeField(key, value);
                    
                    return (
                      <Card key={sectionKey} sx={{ mb: 2 }}>
                        {renderSectionHeader(
                          key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' '),
                          fieldInfo.icon,
                          isExpanded,
                          () => toggleSection(sectionKey)
                        )}
                        <Collapse in={isExpanded}>
                          <CardContent>
                            {renderNestedObject(value, sectionKey)}
                          </CardContent>
                        </Collapse>
                      </Card>
                    );
                  } else {
                    return (
                      <Box key={key} sx={{ mb: 1 }}>
                        {renderKeyValuePair(key, value)}
                      </Box>
                    );
                  }
                })}
              </CardContent>
            </Collapse>
          </Card>
        );
      } else {
        return (
          <Card key={index} sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="body1">{formatValue(item)}</Typography>
            </CardContent>
          </Card>
        );
      }
    });
  };

  const renderExportDialog = () => (
    <Dialog open={exportDialogOpen} onClose={() => setExportDialogOpen(false)} maxWidth="sm" fullWidth>
      <DialogTitle>Export Analysis Results</DialogTitle>
      <DialogContent>
        <Typography variant="body1" sx={{ mb: 2 }}>
          Choose the format for exporting your analysis results:
        </Typography>
        <Stack spacing={2}>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={() => {
              const jsonData = JSON.stringify(data, null, 2);
              const blob = new Blob([jsonData], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'analysis-results.json';
              a.click();
              URL.revokeObjectURL(url);
              setExportDialogOpen(false);
              enqueueSnackbar('Analysis results exported successfully!', { variant: 'success' });
            }}
            fullWidth
          >
            Export as JSON
          </Button>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={() => {
              const csvData = convertToCSV(data);
              const blob = new Blob([csvData], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'analysis-results.csv';
              a.click();
              URL.revokeObjectURL(url);
              setExportDialogOpen(false);
              enqueueSnackbar('Analysis results exported successfully!', { variant: 'success' });
            }}
            fullWidth
          >
            Export as CSV
          </Button>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setExportDialogOpen(false)}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );

  const convertToCSV = (data) => {
    if (!data) return '';
    
    const csvRows = [];
    csvRows.push('Property,Value,Type');
    
    const processObject = (obj, prefix = '') => {
      Object.entries(obj).forEach(([key, value]) => {
        const fullKey = prefix ? `${prefix}.${key}` : key;
        
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          processObject(value, fullKey);
        } else if (Array.isArray(value)) {
          csvRows.push(`${fullKey},"${value.length} items",array`);
        } else {
          csvRows.push(`${fullKey},"${String(value).replace(/"/g, '""')}",${typeof value}`);
        }
      });
    };
    
    const processedData = Array.isArray(data) ? data : [data];
    processedData.forEach((item, index) => {
      if (typeof item === 'object' && item !== null) {
        processObject(item, `Section_${index + 1}`);
      } else {
        csvRows.push(`Value_${index + 1},"${String(item).replace(/"/g, '""')}",${typeof item}`);
      }
    });
    
    return csvRows.join('\n');
  };

  if (!data) return null;

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 2,
            boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
            maxHeight: '90vh'
          }
        }}
      >
        <DialogTitle sx={{ 
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          fontWeight: 'bold',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ComputerIcon />
            {title}
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Export Results">
              <IconButton onClick={() => setExportDialogOpen(true)} sx={{ color: 'white' }}>
                <DownloadIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Copy All Data">
              <IconButton onClick={() => copyToClipboard(JSON.stringify(data, null, 2))} sx={{ color: 'white' }}>
                <CopyIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </DialogTitle>
        
        <DialogContent sx={{ p: 0 }}>
          <Box sx={{ p: 3 }}>
            {renderDynamicContent()}
          </Box>
        </DialogContent>
        
        <DialogActions sx={{ p: 2, backgroundColor: 'rgba(0,0,0,0.02)' }}>
          <Button onClick={onClose} variant="contained" sx={{ textTransform: 'none' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
      
      {renderExportDialog()}
    </>
  );
};

export default BeautifulAnalysisResults;
