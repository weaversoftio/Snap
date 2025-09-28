import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Typography,
  Paper,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Stack,
  Chip,
  Alert,
  AlertTitle
} from '@mui/material';
import { useSnackbar } from 'notistack';
import DialogComponent from '../common/Dialog';
import { Loading } from '../common/loading';
import { CustomerContainer } from '../common/CustomContainer';
import { 
  Add as AddIcon,
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Delete as DeleteIcon,
  Security as SecurityIcon,
  Info as InfoIcon
} from '@mui/icons-material';
import { snapHookApi } from '../../api/snapHookApi';

const SnapHookManagement = ({ clusterName, clusterConfig, onHookSelect }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [snapHooks, setSnapHooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedHook, setSelectedHook] = useState(null);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [newHookData, setNewHookData] = useState({
    name: '',
    webhook_url: '', // Will be auto-generated from SNAP_API_URL
    namespace: 'snap',
    cert_expiry_days: 365
  });
  const [errors, setErrors] = useState({});

  const loadSnapHooks = useCallback(async () => {
    try {
      setLoading(true);
      const response = await snapHookApi.getSnapHooks();
      // Filter SnapHooks by cluster name
      const clusterSnapHooks = response.snaphooks?.filter(hook => hook.cluster_name === clusterName) || [];
      setSnapHooks(clusterSnapHooks);
    } catch (error) {
      enqueueSnackbar('Failed to load SnapHooks', { variant: 'error' });
      console.error('Error loading SnapHooks:', error);
    } finally {
      setLoading(false);
    }
  }, [clusterName, enqueueSnackbar]);

  useEffect(() => {
    if (clusterName) {
      loadSnapHooks();
    }
  }, [clusterName, loadSnapHooks]);

  const handleCreateSnapHook = async () => {
    // Validation
    const validationErrors = {};
    if (!newHookData.name.trim()) {
      validationErrors.name = 'Name is required';
    }
    if (!newHookData.namespace.trim()) {
      validationErrors.namespace = 'Namespace is required';
    }
    if (newHookData.cert_expiry_days < 1 || newHookData.cert_expiry_days > 3650) {
      validationErrors.cert_expiry_days = 'Certificate expiry must be between 1 and 3650 days';
    }

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    try {
      setIsActionLoading(true);
      const hookData = {
        ...newHookData,
        cluster_name: clusterName,
        cluster_config: clusterConfig
      };
      
      await snapHookApi.createSnapHook(hookData);
      enqueueSnackbar('SnapHook created successfully', { variant: 'success' });
      setCreateDialogOpen(false);
      setNewHookData({
        name: '',
        webhook_url: '', // Will be auto-generated from SNAP_API_URL
        namespace: 'snap',
        cert_expiry_days: 365
      });
      setErrors({});
      loadSnapHooks();
    } catch (error) {
      enqueueSnackbar('Failed to create SnapHook', { variant: 'error' });
      console.error('Error creating SnapHook:', error);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleStartSnapHook = async (hookName) => {
    try {
      setIsActionLoading(true);
      await snapHookApi.startSnapHook(hookName);
      enqueueSnackbar(`SnapHook ${hookName} started successfully`, { variant: 'success' });
      loadSnapHooks();
    } catch (error) {
      enqueueSnackbar(`Failed to start SnapHook ${hookName}`, { variant: 'error' });
      console.error('Error starting SnapHook:', error);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleStopSnapHook = async (hookName) => {
    try {
      setIsActionLoading(true);
      await snapHookApi.stopSnapHook(hookName);
      enqueueSnackbar(`SnapHook ${hookName} stopped successfully`, { variant: 'success' });
      loadSnapHooks();
    } catch (error) {
      enqueueSnackbar(`Failed to stop SnapHook ${hookName}`, { variant: 'error' });
      console.error('Error stopping SnapHook:', error);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleDeleteSnapHook = async () => {
    if (!selectedHook) return;
    
    try {
      setIsActionLoading(true);
      await snapHookApi.deleteSnapHook(selectedHook.name);
      enqueueSnackbar(`SnapHook ${selectedHook.name} deleted successfully`, { variant: 'success' });
      setDeleteDialogOpen(false);
      setSelectedHook(null);
      loadSnapHooks();
    } catch (error) {
      enqueueSnackbar(`Failed to delete SnapHook ${selectedHook.name}`, { variant: 'error' });
      console.error('Error deleting SnapHook:', error);
    } finally {
      setIsActionLoading(false);
    }
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
      case 'running': return <StartIcon fontSize="small" />;
      case 'stopped': return <StopIcon fontSize="small" />;
      case 'starting': return <CircularProgress size={16} />;
      case 'error': return <StopIcon fontSize="small" />;
      default: return <StopIcon fontSize="small" />;
    }
  };

  const renderCreateDialog = () => {
    return (
      <DialogComponent open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display="flex" flexDirection="column">
          <Typography variant="h5">Create New SnapHook</Typography>
          <Typography variant="body2" color="text.secondary">
            Create a new SnapHook webhook for automatic pod image redirection.
          </Typography>
          
          <TextField
            label="Name"
            value={newHookData.name}
            onChange={(e) => setNewHookData({ ...newHookData, name: e.target.value })}
            placeholder="Enter SnapHook name"
            error={!!errors.name}
            helperText={errors.name}
            fullWidth
          />
          
          <Alert severity="info" sx={{ mb: 2 }}>
            <AlertTitle>Auto-Generated Webhook URL</AlertTitle>
            The webhook URL will be automatically generated from the SNAP_API_URL environment variable.
            No manual configuration required.
          </Alert>
          
          <TextField
            label="Namespace"
            value={newHookData.namespace}
            onChange={(e) => setNewHookData({ ...newHookData, namespace: e.target.value })}
            placeholder="snap"
            error={!!errors.namespace}
            helperText={errors.namespace}
            fullWidth
          />
          
          <TextField
            label="Certificate Expiry (days)"
            type="number"
            value={newHookData.cert_expiry_days}
            onChange={(e) => setNewHookData({ ...newHookData, cert_expiry_days: parseInt(e.target.value) || 365 })}
            min="1"
            max="3650"
            error={!!errors.cert_expiry_days}
            helperText={errors.cert_expiry_days}
            fullWidth
          />
          
          
          <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
            <Button 
              variant="outlined" 
              onClick={() => setCreateDialogOpen(false)}
              disabled={isActionLoading}
            >
              Cancel
            </Button>
            <Button 
              variant="contained" 
              onClick={handleCreateSnapHook}
              disabled={isActionLoading || !newHookData.name}
            >
              {isActionLoading ? <CircularProgress size={20} /> : 'Create SnapHook'}
            </Button>
          </Stack>
        </Box>
      </DialogComponent>
    );
  };

  const renderDeleteDialog = () => {
    return (
      <DialogComponent open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display="flex" flexDirection="column">
          <Typography variant="h5">Delete SnapHook</Typography>
          <Alert severity="warning">
            <AlertTitle>Warning</AlertTitle>
            Are you sure you want to delete SnapHook "{selectedHook?.name}"? 
            This will stop the webhook and remove all associated resources.
          </Alert>
          
          <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
            <Button 
              variant="outlined" 
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isActionLoading}
            >
              Cancel
            </Button>
            <Button 
              variant="contained" 
              color="error"
              onClick={handleDeleteSnapHook}
              disabled={isActionLoading}
            >
              {isActionLoading ? <CircularProgress size={20} /> : 'Delete'}
            </Button>
          </Stack>
        </Box>
      </DialogComponent>
    );
  };

  if (!clusterName) {
    return (
      <CustomerContainer title="SnapHook Management" subtitle="Manage SnapHook webhooks">
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '50vh',
            textAlign: 'center',
          }}
        >
          <SecurityIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
          <Typography variant="h5" color="primary" sx={{ mb: 2 }}>
            No Cluster Selected
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Select a cluster to manage SnapHook webhooks
          </Typography>
        </Box>
      </CustomerContainer>
    );
  }

  return (
    <CustomerContainer title="SnapHook Management" subtitle={`Manage SnapHook webhooks for ${clusterName}`}>
      {loading ? <Loading /> : (
        <>
          <Button
            variant="contained"
            onClick={() => setCreateDialogOpen(true)}
            sx={{
              backgroundColor: 'primary.main',
              borderRadius: '8px',
              textTransform: 'none',
              mb: 2,
              px: 3,
              py: 1,
              '&:hover': {
                backgroundColor: 'primary.dark',
                boxShadow: 2,
              },
            }}
            startIcon={<AddIcon />}
          >
            Create SnapHook
          </Button>
          
          <Paper elevation={0} sx={{ px: 3, py: 1, bgcolor: 'background.paper', borderRadius: 2 }}>
            {renderCreateDialog()}
            {renderDeleteDialog()}
            
            {snapHooks.length === 0 ? (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: '30vh',
                  textAlign: 'center',
                }}
              >
                <SecurityIcon sx={{ fontSize: 60, color: 'grey.400', mb: 2 }} />
                <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
                  No SnapHooks Found
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Create a SnapHook to get started with automatic pod image redirection.
                </Typography>
              </Box>
            ) : (
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Name</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Webhook URL</TableCell>
                      <TableCell>Namespace</TableCell>
                      <TableCell>Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {snapHooks.map((hook) => (
                      <TableRow 
                        key={hook.name}
                        hover
                        onClick={() => onHookSelect && onHookSelect(hook.name)}
                        sx={{ cursor: 'pointer' }}
                      >
                        <TableCell>
                          <Typography variant="body2" fontWeight="medium">
                            {hook.name}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box
                              sx={{
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                backgroundColor: hook.is_running ? 'success.main' : 'grey.400'
                              }}
                            />
                            <Chip 
                              label={hook.is_running ? 'running' : 'stopped'} 
                              color={getStatusColor(hook.is_running ? 'running' : 'stopped')}
                              size="small"
                              variant="outlined"
                            />
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {hook.webhook_url || 'Auto-generated from SNAP_API_URL'}
                          </Typography>
                        </TableCell>
                        <TableCell>{hook.namespace}</TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Stack direction="row" spacing={1}>
                            {isActionLoading ? (
                              <CircularProgress size={20} />
                            ) : (
                              <>
                                <Tooltip title={hook.is_running ? 'Stop SnapHook' : 'Start SnapHook'}>
                                  <IconButton 
                                    size="small"
                                    color={hook.is_running ? 'warning' : 'success'}
                                    onClick={() => {
                                      hook.is_running 
                                        ? handleStopSnapHook(hook.name)
                                        : handleStartSnapHook(hook.name);
                                    }}
                                  >
                                    {hook.is_running ? <StopIcon fontSize="small" /> : <StartIcon fontSize="small" />}
                                  </IconButton>
                                </Tooltip>
                                
                                <Tooltip title="View Status">
                                  <IconButton 
                                    size="small"
                                    color="info"
                                    onClick={() => {
                                      onHookSelect && onHookSelect(hook.name);
                                    }}
                                  >
                                    <InfoIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                                
                                <Tooltip title="Delete SnapHook">
                                  <IconButton 
                                    size="small"
                                    color="error"
                                    onClick={() => {
                                      setSelectedHook(hook);
                                      setDeleteDialogOpen(true);
                                    }}
                                  >
                                    <DeleteIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </>
                            )}
                          </Stack>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </>
      )}
    </CustomerContainer>
  );
};

export default SnapHookManagement;