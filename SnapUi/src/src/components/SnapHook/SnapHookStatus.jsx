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
  Security as SecurityIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Key as KeyIcon,
  Webhook as WebhookIcon,
  Schedule as ScheduleIcon
} from '@mui/icons-material';
import { snapHookApi } from '../../api/snapHookApi';

const SnapHookStatus = ({ hookName }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    certificate: false,
    webhook: false
  });

  useEffect(() => {
    if (hookName) {
      loadStatus();
    }
  }, [hookName]);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const response = await snapHookApi.getSnapHookStatus(hookName);
      setStatus(response);
    } catch (error) {
      enqueueSnackbar('Failed to load SnapHook status', { variant: 'error' });
      console.error('Error loading SnapHook status:', error);
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
            <SecurityIcon color="primary" />
            <Typography variant="h6">SnapHook Status: {status.name}</Typography>
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
                  {getStatusIcon(status.is_running ? 'running' : 'stopped')}
                  <Box>
                    <Typography variant="subtitle1" fontWeight="medium">
                      Overall Status
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Cluster: {status.cluster_name} | Webhook URL: {status.webhook_url}
                    </Typography>
                  </Box>
                </Stack>
                <Chip 
                  label={status.is_running ? 'running' : 'stopped'} 
                  color={getStatusColor(status.is_running ? 'running' : 'stopped')}
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

        {/* Certificate Status */}
        <Accordion 
          expanded={expandedSections.certificate} 
          onChange={handleSectionChange('certificate')}
          sx={{ mb: 2 }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1} alignItems="center">
              <KeyIcon color="primary" />
              <Typography variant="subtitle1">Certificate Status</Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ pl: 4 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <CheckCircleIcon 
                  color={status.status?.certificate_generated ? 'success' : 'error'} 
                  fontSize="small" 
                />
                <Typography color={status.status?.certificate_generated ? 'success.main' : 'error'}>
                  {status.status?.certificate_generated ? 'Certificate Generated' : 'No Certificate'}
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Expiry Days: {status.cert_expiry_days}
              </Typography>
            </Box>
          </AccordionDetails>
        </Accordion>


        {/* Webhook Status */}
        <Accordion 
          expanded={expandedSections.webhook} 
          onChange={handleSectionChange('webhook')}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1} alignItems="center">
              <WebhookIcon color="primary" />
              <Typography variant="subtitle1">Webhook Status</Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ pl: 4 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <CheckCircleIcon 
                  color={status.is_running ? 'success' : 'error'} 
                  fontSize="small" 
                />
                <Typography color={status.is_running ? 'success.main' : 'error'}>
                  {status.is_running ? 'HTTPS Server Running' : 'HTTPS Server Stopped'}
                </Typography>
              </Stack>
              <Box sx={{ mt: 2 }}>
                <Divider sx={{ mb: 1 }} />
                <Stack spacing={1}>
                  <Typography variant="body2">
                    Webhook URL: {status.webhook_url}
                  </Typography>
                  <Typography variant="body2">
                    Namespace: {status.namespace}
                  </Typography>
                  <Typography variant="body2">
                    HTTPS Port: {status.status?.https_server_port || 'Not running'}
                  </Typography>
                  <Typography variant="body2">
                    Certificate Generated: {status.status?.certificate_generated ? '✓' : '✗'}
                  </Typography>
                </Stack>
              </Box>
            </Box>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  );
};

export default SnapHookStatus;