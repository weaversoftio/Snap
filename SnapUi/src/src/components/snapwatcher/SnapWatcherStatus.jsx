import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardHeader,
  Button,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Alert,
  AlertTitle,
  Stack,
  Divider
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { 
  ExpandMore as ExpandMoreIcon,
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Schedule as ScheduleIcon,
  Computer as ComputerIcon,
  AccountTree as AccountTreeIcon,
  Storage as StorageIcon
} from '@mui/icons-material';
import { snapWatcherApi } from '../../api/snapWatcherApi';

const SnapWatcherStatus = ({ watcherName }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    cluster: false,
    configuration: false,
    monitoring: false
  });

  useEffect(() => {
    if (watcherName) {
      loadStatus();
    }
  }, [watcherName]);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const response = await snapWatcherApi.getSnapWatcherStatus(watcherName);
      setStatus(response);
    } catch (error) {
      enqueueSnackbar('Failed to load SnapWatcher status', { variant: 'error' });
      console.error('Error loading SnapWatcher status:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSectionChange = (section) => (event, isExpanded) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: isExpanded
    }));
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return 'success';
      case 'stopped': return 'default';
      case 'starting': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running': return <CheckCircleIcon color="success" />;
      case 'stopped': return <ErrorIcon color="disabled" />;
      case 'starting': return <ScheduleIcon color="warning" />;
      case 'error': return <ErrorIcon color="error" />;
      default: return <WarningIcon color="disabled" />;
    }
  };

  if (!status) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
          <Typography variant="body1" sx={{ ml: 2 }}>Loading status...</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={
          <Stack direction="row" spacing={1} alignItems="center">
            <VisibilityIcon color="primary" />
            <Typography variant="h6">SnapWatcher Status: {status.name}</Typography>
          </Stack>
        }
        action={
          <Button
            size="small"
            variant="outlined"
            onClick={loadStatus}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
          >
            Refresh
          </Button>
        }
      />
      <CardContent>
        {/* Overall Status */}
        <Box sx={{ mb: 3 }}>
          <Card variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Stack direction="row" spacing={2} alignItems="center">
                {getStatusIcon(status.status)}
                <Box>
                  <Typography variant="subtitle1" fontWeight="medium">
                    Overall Status
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Cluster: {status.cluster_name} | Scope: {status.scope}{status.scope !== 'cluster' ? ` | Namespace: ${status.namespace}` : ''}
                  </Typography>
                </Box>
              </Stack>
              <Chip 
                label={status.status} 
                color={getStatusColor(status.status)}
                variant="outlined"
              />
            </Stack>
          </Card>
        </Box>

        {status.error_message && (
          <Alert severity="error" sx={{ mb: 3 }}>
            <AlertTitle>Error</AlertTitle>
            {status.error_message}
          </Alert>
        )}

        {/* Cluster Configuration */}
        <Accordion 
          expanded={expandedSections.cluster} 
          onChange={handleSectionChange('cluster')}
          sx={{ mb: 2 }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1} alignItems="center">
              <ComputerIcon color="primary" />
              <Typography variant="subtitle1">Cluster Configuration</Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ pl: 4 }}>
              <Stack spacing={2}>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Cluster Name
                  </Typography>
                  <Typography variant="body1">
                    {status.cluster_name}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    API Server URL
                  </Typography>
                  <Typography variant="body1">
                    {status.cluster_config?.cluster_config_details?.kube_api_url || 
                     status.cluster_config?.api_server_url || 'Not configured'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Authentication Type
                  </Typography>
                  <Typography variant="body1">
                    {status.cluster_config?.cluster_config_details?.token ? 'Token' : 
                     status.cluster_config?.auth_type || 'Not configured'}
                  </Typography>
                </Box>
              </Stack>
            </Box>
          </AccordionDetails>
        </Accordion>

        {/* Watcher Configuration */}
        <Accordion 
          expanded={expandedSections.configuration} 
          onChange={handleSectionChange('configuration')}
          sx={{ mb: 2 }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1} alignItems="center">
              <AccountTreeIcon color="primary" />
              <Typography variant="subtitle1">Watcher Configuration</Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ pl: 4 }}>
              <Stack spacing={2}>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Scope
                  </Typography>
                  <Typography variant="body1">
                    {status.scope}
                  </Typography>
                </Box>
                {status.scope !== 'cluster' && (
                  <Box>
                    <Typography variant="body2" fontWeight="medium" color="text.secondary">
                      Namespace
                    </Typography>
                    <Typography variant="body1">
                      {status.namespace}
                    </Typography>
                  </Box>
                )}
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Trigger Type
                  </Typography>
                  <Typography variant="body1">
                    {status.trigger || 'startupProbe'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Auto Delete Pod
                  </Typography>
                  <Typography variant="body1">
                    {status.auto_delete_pod ? 'Enabled' : 'Disabled'}
                  </Typography>
                </Box>
              </Stack>
            </Box>
          </AccordionDetails>
        </Accordion>

        {/* Monitoring Status */}
        <Accordion 
          expanded={expandedSections.monitoring} 
          onChange={handleSectionChange('monitoring')}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1} alignItems="center">
              <StorageIcon color="primary" />
              <Typography variant="subtitle1">Monitoring Status</Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ pl: 4 }}>
              <Stack spacing={2}>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Thread Status
                  </Typography>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CheckCircleIcon 
                      color={status.status === 'running' ? 'success' : 'error'} 
                      fontSize="small" 
                    />
                    <Typography color={status.status === 'running' ? 'success.main' : 'error'}>
                      {status.status === 'running' ? 'Thread Active' : 'Thread Inactive'}
                    </Typography>
                  </Stack>
                </Box>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Last Update
                  </Typography>
                  <Typography variant="body1">
                    {status.last_update ? new Date(status.last_update).toLocaleString() : 
                     status.updated_at ? new Date(status.updated_at).toLocaleString() : 'Never'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" fontWeight="medium" color="text.secondary">
                    Created At
                  </Typography>
                  <Typography variant="body1">
                    {status.created_at ? new Date(status.created_at).toLocaleString() : 'Unknown'}
                  </Typography>
                </Box>
              </Stack>
            </Box>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  );
};

export default SnapWatcherStatus;
